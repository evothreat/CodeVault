#ifndef CMDTYPES_H
#define CMDTYPES_H

typedef enum {
	NEW_PUBLISHER,
	PUBLISH,
	SUBSCRIBE
} pubsub_cmd_t;

typedef struct {
	pubsub_cmd_t cmd;
	char		 product_name[100];
	int 		 price;
} pubsub_new_publisher_t;

typedef struct {
	pubsub_cmd_t cmd;
	char 		 publication[10000];
} pubsub_publish_t;

typedef struct {
	pubsub_cmd_t cmd;
	char 		 product_name[100];
	int 		 paid;
} pubsub_subscribe_t;

// ------------------------------------------------------------------

typedef enum {
	PORT,
	PUBLICATION,
	NO_SUCH_PRODUCT,
	PAY_MORE
} server_cmd_t;

typedef struct {
	server_cmd_t   cmd;
	unsigned short port;
} server_port_t;

typedef struct {
	server_cmd_t cmd;
} server_no_product_t;

typedef struct {
	server_cmd_t cmd;
	int 		 missing_amount;
} server_pay_more_t;

typedef struct {
	server_cmd_t cmd;
	char 		 publication[10000];
} server_publication_t;

#endif