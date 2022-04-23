#ifndef UTILS_H
#define UTILS_H

#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>

#define check(isErr, msg) 				\
			if ((isErr)) {				\
				perror((msg));			\
				exit(EXIT_FAILURE);}

#define SOCKADDR(addr)	(struct sockaddr*) &(addr)


#define REGPORT 8888
#define REGADDR "127.0.0.1"


int read_cmd(char* buf);

#endif