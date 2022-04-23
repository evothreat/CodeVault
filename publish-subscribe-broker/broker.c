#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <sys/socket.h>
#include <sys/select.h>
#include <sys/fcntl.h>
#include <sys/time.h>
#include <pthread.h>
#include "list.h"
#include "cmd-types.h"
#include "common.h"

#define TIMEOUT 5
#define BUFLEN 520

// ------------------------------------------------------------------

typedef struct {
	int 	  		 sock;
	char 	  		 product_name[100];
	int 	  		 price;
	struct list_head subscribers;
	struct list_head lh;
} publisher_t;

typedef struct {
	struct sockaddr_in addr;
	int 			   addrlen;
	struct list_head   lh;
} subscriber_t;

struct list_head publishers = LIST_HEAD_INIT(publishers);

// ------------------------------------------------------------------

typedef struct {
	int 			   from_sock;
	struct sockaddr_in from_addr;
	int 			   addrlen;
	void*			   body;
	void*			   other;
} request_t;

typedef void* (*handler_t)(request_t*);

// ------------------------------------------------------------------

publisher_t* find_pub_by_product(char* name)
{
	for (struct list_head* it = publishers.next; it != &publishers; it = it->next) {
			publisher_t* pub = container_of(it, publisher_t, lh);
			if (strcmp(pub->product_name, name) == 0)
				return pub;
		}
	return NULL;
}

subscriber_t* find_subscr_by_addr(publisher_t* pub, struct sockaddr_in addr)
{
	for (struct list_head* it = pub->subscribers.next; it != &pub->subscribers; it = it->next) {
			subscriber_t* subscr = container_of(it, subscriber_t, lh);
			if (subscr->addr.sin_addr.s_addr == addr.sin_addr.s_addr && 
				subscr->addr.sin_port == addr.sin_port)
				return subscr;
		}
	return NULL;
}

void* handle_new_publisher(request_t* req)
{
	pubsub_new_publisher_t* data = req->body;

	// product with that name exist already
	//if (find_pub_by_product(data->product_name))
	//	goto end;	// need to reply

	publisher_t* pub = malloc(sizeof(publisher_t));
	pub->sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
	check(pub->sock < 0, "handle_new_publisher: socket");

	struct sockaddr_in addr;
	int addrlen = sizeof(addr);
	
	memset(&addr, 0, addrlen);
	addr.sin_family = AF_INET;
	addr.sin_port = 0;
	addr.sin_addr.s_addr = htonl(INADDR_ANY);
	
	check(bind(pub->sock, SOCKADDR(addr), addrlen) < 0, "handle_new_publisher: bind");
	// get bound address
	check(getsockname(pub->sock, SOCKADDR(addr), &addrlen) < 0, "handle_new_publisher: getsockname");

	strncpy(pub->product_name, data->product_name, sizeof(pub->product_name));
	pub->price = data->price;
	INIT_HEAD(&pub->subscribers);

	// add to global list
	list_add(&publishers, &pub->lh);

	// resp
	server_port_t resp = {.cmd=PORT, .port=ntohs(addr.sin_port)};
	check(sendto(req->from_sock, &resp, sizeof(resp), 0,
				SOCKADDR(req->from_addr), req->addrlen) < 0, "handle_new_publisher: sendto");
	end:
	free(data);
	free(req);
	return NULL;
}

void* handle_subscribe(request_t* req)
{
	pubsub_subscribe_t* data = req->body;

	publisher_t* pub = find_pub_by_product(data->product_name);
	if (!pub) {
		server_no_product_t resp = {.cmd=NO_SUCH_PRODUCT};
		check(sendto(req->from_sock, &resp, sizeof(resp), 0, 
					  SOCKADDR(req->from_addr), req->addrlen) < 0, "handle_subscribe: sendto");
		goto end;
	}
	
	if (find_subscr_by_addr(pub, req->from_addr))
		goto end;	// already subscribed

	if (pub->price > data->paid) {
		server_pay_more_t resp = {.cmd=PAY_MORE, .missing_amount=pub->price - data->paid};
		check(sendto(req->from_sock, &resp, sizeof(resp), 0, 
					  SOCKADDR(req->from_addr), req->addrlen) < 0, "handle_subscribe: sendto");
		goto end;
	}
	// allocate space for publisher and store
	subscriber_t* subscr = malloc(sizeof(subscriber_t));
	subscr->addr = req->from_addr;
	subscr->addrlen = req->addrlen;
	list_add(&pub->subscribers, &subscr->lh);

	end:
	free(data);
	free(req);
	return NULL;
}

void* handle_publish(request_t* req)
{
	// simply change cmd of request (to save up memory allocation and copying)
	server_publication_t* resp = req->body;
	resp->cmd = PUBLICATION;

	publisher_t* pub = req->other;
	for (struct list_head* it = pub->subscribers.next; it != &pub->subscribers; it = it->next) {
			subscriber_t* subscr = container_of(it, subscriber_t, lh);
			check(sendto(pub->sock, resp, sizeof(server_publication_t), 0, 
				  SOCKADDR(subscr->addr), subscr->addrlen) < 0, "handle_publish: sendto");
	}

	free(resp);
	free(req);
	return NULL;
}

void* pub_port_listener(void* args)
{
	char* buf = NULL;
	const int buflen = sizeof(pubsub_publish_t);

	fd_set readfds;
	while(1)
	{
		FD_ZERO(&readfds);
		int maxfd = -1;

		for (struct list_head* it = publishers.next; it != &publishers; it = it->next) {
			publisher_t* pub = container_of(it, publisher_t, lh);
			FD_SET(pub->sock, &readfds);
			maxfd = pub->sock > maxfd ? pub->sock : maxfd;
		}

		// listen all sockets
		struct timeval tv = {.tv_sec=TIMEOUT, .tv_usec=0};
		int active = select(maxfd + 1, &readfds, NULL, NULL, &tv);
		check(active < 0 && errno != EINTR, "pub_port_listener: select");		// remove errno?

		// after timeout, refresh listened sockets list
		if (!active)
			continue;

		for (struct list_head* it = publishers.next; it != &publishers; it = it->next) {
			publisher_t* pub = container_of(it, publisher_t, lh);
			if (!FD_ISSET(pub->sock, &readfds))
				continue;

			// if allocated memory is used by handle_publish function, allocate new
			buf = !buf ? malloc(buflen) : buf;
			int datalen = recvfrom(pub->sock, buf, buflen, 0, NULL, NULL);
			check(datalen < 0, "pub_port_listener: recvfrom");

			if (datalen == sizeof(pubsub_publish_t) && read_cmd(buf) == PUBLISH) {
				request_t* req = malloc(sizeof(request_t));
				req->body = buf;
				req->other = pub;
				buf = NULL;
				// handle request
				pthread_t tid;
				check(pthread_create(&tid, NULL, (void* (*)(void*)) handle_publish, req) < 0, 
					  "pub_port_listener: pthread_create");
			}
		}
	}
	return NULL;
}

void* reg_port_listener(void* args)
{	
	int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
	check(sock < 0, "reg_port_listener: socket");
	
	struct sockaddr_in local_addr, remote_addr;
	int addrlen = sizeof(remote_addr);

	memset(&local_addr, 0, addrlen);							// need this?
	local_addr.sin_family = AF_INET;
	local_addr.sin_port = htons(REGPORT);
	local_addr.sin_addr.s_addr = htonl(INADDR_ANY);

	check(bind(sock, SOCKADDR(local_addr), addrlen) < 0, "reg_port_listener: bind");

	while (1) {
		char buf[BUFLEN];
		int datalen = recvfrom(sock, buf, BUFLEN, 0, SOCKADDR(remote_addr), &addrlen);
		check(datalen < 0, "reg_port_listener: recvfrom");	

		handler_t handler = NULL;

		int cmd = read_cmd(buf);
		// check size to avoid
		if (datalen == sizeof(pubsub_new_publisher_t) && cmd == NEW_PUBLISHER)
			handler = handle_new_publisher;
		else if (datalen == sizeof(pubsub_subscribe_t) && cmd == SUBSCRIBE)		
			handler = handle_subscribe;

		if (handler) {
			request_t* req = malloc(sizeof(request_t));
			req->from_sock = sock;
			req->from_addr = remote_addr;
			req->addrlen = addrlen;
			req->body = malloc(datalen);
			memcpy(req->body, buf, datalen);

			pthread_t tid;
			check(pthread_create(&tid, NULL, (void* (*)(void*)) handler, req) < 0, 
				  "reg_port_listener: pthread_create");
		}
	}
	close(sock);	// break loop to close socket
	return NULL;
}

int main(void)
{
	pthread_t tid0, tid1;

	pthread_create(&tid0, NULL, reg_port_listener, NULL);
	pthread_create(&tid1, NULL, pub_port_listener, NULL);

	pthread_join(tid0, NULL);
	pthread_join(tid1, NULL);
	return 0;
}