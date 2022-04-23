#include "directory-simulation.h"
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <stdbool.h>

// size of metadata
#define METASIZE 8

// file types
#define MAX_TYPES 8

#define UNKNOWN 0
#define REG 	1
#define DIR 	2
#define CHR 	3
#define BLK 	4
#define FIFO	5
#define SOCK	6
#define LNK		7	

/*
all are unsigned
inode number - 4 bytes
rec length - 2 bytes
name length - 1 byte
file type - 1 byte
file name - 255 bytes
*/

int inode_num = 1;

/*
	Returns unique inode number for this library.
	@return Unique inode number.
*/
int get_unique_inode()
{
	return inode_num++;
}

/*
	Calculates length of pad needed to add to the string.
	@param name_len Length of name which will be padded.
	@return Pad length needed to add.
*/
int calc_pad_len(const uint8_t name_len)
{
	int r = name_len % 4;
	return r == 0 ? 0 : (4 - r);
}

/*
	Splits 32 bit unsigned integer into 4 bytes.
	@param buf Buffer to store the bytes.
	@param x Number to split.
*/
void split_uint32(uint8_t* const buf, const uint32_t x)
{
	buf[0] = x & 0xFF;
	buf[1] = x >> 8 & 0xFF;
	buf[2] = x >> 16 & 0xFF;
	buf[3] = x >> 24 & 0xFF;
}


/*
	Splits 16 bit unsigned integer into 2 bytes.
	@param buf Buffer to store the bytes.
	@param x Number to split.
*/
void split_uint16(uint8_t* const buf, const uint16_t x)
{
	buf[0] = x & 0xFF;
	buf[1] = x >> 8 & 0xFF;
}

/*
	Reads record from directory file and sets file pointer to the next record.
	@param dir Descriptor of file to search in.
	@param rec Record structure to store the record.
	@return Offset to the next record or -1 if error occured.
*/
int read_record(const int dir, struct Record* const rec)
{
	uint8_t meta[METASIZE];
	if (read(dir, meta, METASIZE) < 1) return -1;
	rec->inode    = meta[0] | meta[1] << 8 | meta[2] << 16 | meta[3] << 24;
	rec->rec_len  = meta[4] | meta[5] << 8;
	rec->name_len = meta[6];
	rec->type     = meta[7];
	if (read(dir, rec->name, rec->name_len) < 1) return -1;
	rec->name[rec->name_len] = '\0';
	return lseek(dir, rec->rec_len - rec->name_len - METASIZE, SEEK_CUR);
}

/*
	Searches for record in directory file and returns its offset if found.
	@param dir Descriptor of file to search in.
	@param name Name of record to search.
	@return Offset of found record or -1 if record doesnt exist or error occured.
*/
int find_record(const int dir, uint8_t* const name) 
{
	struct Record rec;
	lseek(dir, 0, SEEK_SET);
	while (read_record(dir, &rec) > 0) {
		if (rec.inode > 0 && strcmp(rec.name, name) == 0) {
			return lseek(dir, -rec.rec_len, SEEK_CUR);
		}
	}
	return -1;
}

/*
	Deletes record from directory file. If the record doesnt have predecessor, 
	then the number is set to the zero, else the record length is added 
	to the previous record.
	@param dir Descriptor of file to search in.
	@param name Name of record to search.
	@return Non-negative value if record succesfully deleted, else -1.
*/
int delete_record(const int dir, uint8_t* const name, bool types[])
{
	uint16_t prev_rec_len = 0;
	struct Record rec;
	lseek(dir, 0, SEEK_SET);
	while (read_record(dir, &rec) > 0) {
		if (rec.inode > 0 && strcmp(rec.name, name) == 0 && types[rec.type]) {
			if (prev_rec_len == 0) {
				lseek(dir, -rec.rec_len, SEEK_CUR);
				uint8_t new_inode[4] = {0,0,0,0};
				return write(dir, new_inode, 4);
			}
			lseek(dir, -(rec.rec_len + prev_rec_len - 4), SEEK_CUR);
			uint8_t new_prev_len[2];
			split_uint16(new_prev_len, rec.rec_len + prev_rec_len);
			return write(dir, new_prev_len, 2);
		}
		prev_rec_len = rec.rec_len;
	}
	return -1;
}

/*
	Appends record with given name, type and inode number to the end of file.
	@param dir Descriptor of file to write in.
	@param name Name of new record.
	@param type Type of new record.
	æparam inode Inode-number of new record.
	@return Non-negative value if success and -1 if writing failed.
*/
int add_record(const int dir, uint8_t* const name, const uint8_t type, const uint32_t inode)
{
	uint8_t name_len = strlen(name);
	// name length overflowed?
	if (name_len < 0) return -1;
	uint8_t pad_len = calc_pad_len(name_len);
	uint16_t rec_len = METASIZE + name_len + pad_len;
	uint8_t rec[rec_len];
	split_uint32(rec, inode < 1 ? get_unique_inode() : inode);
	split_uint16(rec + 4, rec_len);
	rec[6] = name_len;
	rec[7] = type;
	strncpy(rec + METASIZE, name, name_len);				// or call write() twice
	memset(rec + METASIZE + name_len, '\0', pad_len);
	lseek(dir, 0, SEEK_END);
	return write(dir, rec, rec_len);
}

int sim_creat(char* const name)
{
	int dir = open("directory.sim", O_RDWR);
	if (dir < 0) return -1;
	if (find_record(dir, name) >= 0) {
		close(dir);
		return -1;
	}
	add_record(dir, name, REG, 0);
	return close(dir);
}

int sim_mkdir(char* const name)
{
	int dir = open("directory.sim", O_RDWR);
	if (dir < 0) return -1;
	if (find_record(dir, name) >= 0) {
		close(dir);
		return -1;
	}
	add_record(dir, name, DIR, 0);
	return close(dir);
}

int sim_rmdir(char* const name)
{
	int dir = open("directory.sim", O_RDWR);
	if (dir < 0) return -1;
	bool types[MAX_TYPES] = {false};						// set other to zero!!!
	types[DIR] = true;
	delete_record(dir, name, types);
	return close(dir);
}

int sim_link(char* const name, char* const linkname)
{
	int dir = open("directory.sim", O_RDWR);
	if (dir < 0) return -1;
	// if link already exists or file doesnt exist
	if (find_record(dir, linkname) >= 0 || find_record(dir, name) < 0){
		close(dir);
		return -1;
	}
	struct Record rec;
	read_record(dir, &rec);
	// if not regular file
	if (rec.type != REG) {
		close(dir);
		return -1;
	}
	add_record(dir, linkname, rec.type, rec.inode);
	return close(dir);
}

int sim_unlink(char* const name)
{
	int dir = open("directory.sim", O_RDWR);
	if (dir < 0) return -1;
	bool types[MAX_TYPES] = {false};
	types[REG] = true;								// hardlinks
	types[LNK] = true;
	delete_record(dir, name, types);
	return close(dir);
}

int sim_symlink(char* const name, char* const linkname)
{
	int dir = open("directory.sim", O_RDWR);
	if (dir < 0) return -1;
	if (find_record(dir, linkname) >= 0 || find_record(dir, name) < 0) {
		close(dir);
		return -1;
	}
	struct Record rec;
	read_record(dir, &rec);
	add_record(dir, linkname, LNK, rec.inode);
	return close(dir);	
}

int sim_rename(char* const name, char* const newname)
{
	int dir = open("directory.sim", O_RDWR);
	if (dir < 0) return -1;
	if (find_record(dir, name) < 0) {
		close(dir);
		return -1;
	}
	struct Record rec;
	read_record(dir, &rec);
	bool types[MAX_TYPES] = {false};
	types[rec.type] = true;
	delete_record(dir, rec.name, types);
	add_record(dir, newname, rec.type, rec.inode);
	return close(dir);
}