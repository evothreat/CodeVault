#ifndef DIRECTORY_SIMULATION_H
#define DIRECTORY_SIMULATION_H

#include <stdint.h>

struct Record {
	uint32_t inode;
	uint16_t rec_len;
	uint8_t	 name_len;
	uint8_t  type;
	uint8_t  name[256];
};
int read_record(const int dir, struct Record* const rec);


int sim_creat(char* const name);
int sim_mkdir(char* const name);
int sim_rmdir(char* const name);
int sim_link(char* const name, char* const linkname);
int sim_unlink(char* const name);
int sim_symlink(char* const name, char* const linkname);
int sim_rename(char* const name, char* const newname);

#endif