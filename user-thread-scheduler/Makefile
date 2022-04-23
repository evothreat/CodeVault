all: test clean

test: test.o scheduler.o
	gcc test.o scheduler.o -o test -pthread
test.o: test.c scheduler.h
	gcc -c test.c
directory-simulation.o: scheduler.c scheduler.h
	gcc -c directory-simulation.c
clean:
	rm -f *.o
