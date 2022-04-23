#include "directory-simulation.h"
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>

int main(int argc, char const *argv[])
{
	int dir = open("directory.sim", O_RDONLY);
	if (dir < 0) {
		printf("directory.sim doesnt exist\n");
		return -1;
	}
	struct Record rec;
	while (read_record(dir, &rec) > 0) {
		if (rec.inode > 0) printf("%d%s\n", rec.type, rec.name);
	}
	return close(dir);
}