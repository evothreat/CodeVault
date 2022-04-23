#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <sys/socket.h>
#include "cmd-types.h"
#include "common.h"

#define BUFLEN 512


int reg_new_publisher(char const* product_name, const int price)
{ 	
  	int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  	check(sock < 0, "reg_new_publisher: socket");

  	struct sockaddr_in addr;
    int addrlen = sizeof(struct sockaddr_in); 

    memset(&addr, 0, addrlen);
    addr.sin_family = AF_INET;
    addr.sin_port = htons(REGPORT);
    addr.sin_addr.s_addr = inet_addr(REGADDR);
      
    pubsub_new_publisher_t req = {.cmd=NEW_PUBLISHER, .price=price};
    strncpy(req.product_name, product_name, sizeof(req.product_name));
      
    check(sendto(sock, &req, sizeof(req), 0, SOCKADDR(addr), addrlen) < 0, 
    			 "reg_new_publisher: sendto"); 
    
    server_port_t resp;
    recvfrom(sock, &resp, sizeof(resp), 0, SOCKADDR(addr), &addrlen);

    close(sock); 
    return resp.port;
}

void input_handler(const int port)
{
	// initialize socket here
	int sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
  	check(sock < 0, "input_handler: socket");

  	struct sockaddr_in addr;
    int addrlen = sizeof(struct sockaddr_in); 

    memset(&addr, 0, addrlen);
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    addr.sin_addr.s_addr = inet_addr(REGADDR);
	
	pubsub_publish_t req = {.cmd=PUBLISH};

	while (1) {
		printf("new-pub> ");
		fflush(stdout);

		fgets(req.publication, sizeof(req.publication), stdin);

		if (req.publication[0] == '\n')
			continue;

		// send to the server
        // TODO: do not send whole buffer, only the data! (or set max send/receive data size in one step)
		check(sendto(sock, &req, sizeof(req), 0, SOCKADDR(addr), addrlen) < 0, 
    			 "input_handler: sendto");

		printf("publication sent succesfully\n");
	}
	close(sock);
}

int main(int argc, char const *argv[])
{
	if (argc < 3) {
		printf("Usage: ./publisher <id> <product_name> <product_price>\n");
		return 0;
	}
	// argv[2] == product_name, argv[3] == price
	int port = reg_new_publisher(argv[2], atoi(argv[3]));

	printf("port to listen is %d\n", port);

	input_handler(port);
	return 0;
}