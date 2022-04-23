#include <iostream>
#include <algorithm>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#define check(isErr, msg) 			\
			if ((isErr)) {			\
				perror((msg));		\
				exit(EXIT_FAILURE);}

#define DEST_FILE_PERM 0644


using namespace std;

const size_t PAGESIZE = (size_t) sysconf(_SC_PAGESIZE);


/**
 * 	Liefert die Anzahl der Bytes in einer Datei.
 *
 *	@param fd Deskriptor der Datei.
 *	@return Anzahl der Bytes in der Datei.
 */
static size_t getFileSize(int fd)
{
	size_t currOff = lseek(fd, 0, SEEK_CUR);
	size_t size = lseek(fd, 0, SEEK_END);
	lseek(fd, currOff, SEEK_SET);
	return size;
}

/**
 * 	Berechnet den Beginn einer Speicherseite anhand des Offsets.
 *
 *	@param off Offset in der Datei.
 *	@return Offset/Beginn der Speicherseite.
 */
static size_t getPrevPageOff(size_t off)
{
	if (off == 0 || off < PAGESIZE)
		return 0;
	size_t r = off % PAGESIZE;
	return off - (r == 0 ? PAGESIZE : r);
}

int main(int argc, char const *argv[])
{
	if (argc < 3) {
		cout << "Usage: ./kopfstand <source_file> <destination_file>" << endl;
		return EXIT_SUCCESS;
	}
	int srcFile = open(argv[1], O_RDONLY);
	check(srcFile < 0, "Failed to open source file for reading");

	size_t dataLen = getFileSize(srcFile);
	if (dataLen == 0) {
		cout << "The source file is empty" << endl;
		close(srcFile);
		return EXIT_FAILURE;
	}
	int dstFile = open(argv[2], O_RDWR | O_CREAT | O_TRUNC, DEST_FILE_PERM);
	check(srcFile < 0, "Failed to open destination file for writing");
	
	check(ftruncate(dstFile, dataLen) < 0, "Failed to extend destination file");

	size_t srcFileOff = getPrevPageOff(dataLen);
	char* srcPage = NULL;
	int srcMapLen = dataLen - srcFileOff;
	int srcPageOff = srcMapLen - 1;

	size_t dstFileOff = 0;
	int dstPageOff = 0;
	char* dstPage = NULL;
	int dstMapLen = min(dataLen, PAGESIZE);

	while (dataLen > 0) {
		if (srcPage == NULL) {
			srcPage = (char*) mmap(NULL, srcMapLen, PROT_READ, MAP_PRIVATE, srcFile, srcFileOff);
			check(srcPage == MAP_FAILED, "Failed to load source file page");
		}
		if (dstPage == NULL) {
			dstPage = (char*) mmap(NULL, dstMapLen, PROT_READ | PROT_WRITE, MAP_SHARED, dstFile, dstFileOff);
			check(dstPage == MAP_FAILED, "Failed to load destination file page");
		}
		while (srcPageOff >= 0 && dstPageOff < dstMapLen) {
			dstPage[dstPageOff++] = srcPage[srcPageOff--];
			dataLen--;
		}
		if (srcPageOff < 0) {
			srcFileOff = getPrevPageOff(srcFileOff);
			check(munmap(srcPage, srcMapLen) < 0, "Failed to unload source file page");
			srcPage = NULL;
			srcMapLen = min(dataLen, PAGESIZE);
			srcPageOff = srcMapLen - 1;
		}
		if (dstPageOff == dstMapLen) {
			dstFileOff += dstMapLen;
			dstPageOff = 0;
			check(munmap(dstPage, dstMapLen) < 0, "Failed to unload destination file page");
			dstPage = NULL;
			dstMapLen = min(dataLen, PAGESIZE);
		}
	}
	close(srcFile);
	close(dstFile);
	return EXIT_SUCCESS;
}