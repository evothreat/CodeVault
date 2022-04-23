all: broker publisher subscriber

broker: broker.c common.c cmd-types.h list.h
	gcc -o broker broker.c common.c -pthread

publisher: publisher.c common.c cmd-types.h list.h
	gcc -o publisher publisher.c common.c -pthread

subscriber: subscriber.c common.c cmd-types.h list.h
	gcc -o subscriber subscriber.c common.c -pthread

clean:
	rm -f *.gch