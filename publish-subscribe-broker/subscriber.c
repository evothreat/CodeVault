#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <sys/socket.h>
#include <pthread.h>
#include "cmd-types.h"
#include "common.h"

#define BUFLEN 10240


void* input_handler(void* args)
{	
	int sock = *((int*) args);

	struct sockaddr_in addr;
	int addrlen = sizeof(addr);

    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(REGPORT);
    addr.sin_addr.s_addr = inet_addr(REGADDR);

	pubsub_subscribe_t req = {.cmd=SUBSCRIBE};

	while (1) {
		printf("sub> ");
		fflush(stdout);

		char line[128];
		fgets(line, sizeof(line), stdin);

		if (sscanf(line, "%s %d", req.product_name, &req.paid) < 2)
			continue;

		check(sendto(sock, &req, sizeof(req), 0, SOCKADDR(addr), sizeof(addr)) < 0, 
    			 "input_handler: sendto");

		printf("you subscribed succesfully\n");
	}
	return NULL;
}

void* publication_listener(void* args)
{
	int sock = *((int*) args);

	struct sockaddr_in addr;
	int addrlen = sizeof(addr);

    memset(&addr, 0, addrlen);
    addr.sin_family = AF_INET;
    addr.sin_port = htons(REGPORT);
    addr.sin_addr.s_addr = inet_addr(REGADDR);

    while (1) {
    	char buf[BUFLEN];
    	check(recvfrom(sock, buf, BUFLEN, 0, SOCKADDR(addr), &addrlen) < 0, "publication_listener: recvfrom");

    	int cmd = read_cmd(buf);
    	if (cmd == PUBLICATION) {
    		server_publication_t* resp = (server_publication_t*) buf;
    		printf("\nnew publication: %s\n", resp->publication);
    	}
    	else if (cmd == NO_SUCH_PRODUCT) {
    		printf("\nsuch product doesnt exist\n");
    	}
    	else if (cmd == PAY_MORE) {
    		server_pay_more_t* resp = (server_pay_more_t*) buf;
			printf("\nyou need to pay %d more\n", resp->missing_amount);
    	}
    }
    return NULL;
}

int main(int argc, char const *argv[])
{
	if (argc < 2) {
		printf("Usage: ./subscriber <id>\n");
		return 0;
	}
	int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  	check(sock < 0, "main: socket");

	pthread_t tid0, tid1;

	pthread_create(&tid0, NULL, input_handler, (void*) &sock);
	pthread_create(&tid1, NULL, publication_listener, (void*) &sock);

	pthread_join(tid0, NULL);
	pthread_join(tid1, NULL);

	close(sock);
	return 0;
}