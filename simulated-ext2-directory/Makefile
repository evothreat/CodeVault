all: test sim_ls

test: test.o directory-simulation.o
	gcc test.o directory-simulation.o -o test
test.o: test.c directory-simulation.h
	gcc -c test.c
sim_ls: sim_ls.o directory-simulation.o
	gcc sim_ls.o directory-simulation.o -o sim_ls
sim_ls.o: sim_ls.c directory-simulation.h
	gcc -c sim_ls.c
directory-simulation.o: directory-simulation.c directory-simulation.h
	gcc -c directory-simulation.c
clean:
	rm -f *.o
