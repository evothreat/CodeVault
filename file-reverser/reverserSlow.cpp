#include <iostream>
#include <cstdlib>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#define DEST_FILE_PERM 0644

using namespace std;

const size_t PAGESIZE = (size_t) sysconf(_SC_PAGESIZE);

/**
 *	Überprüft, ob der Fehler-Flag auf true gesetzt ist und falls ja, 
 *	beendet das Programm und gibt die übergebene Nachricht aus.
 *	
 *	@param isErr Fehler-Flag.
 *	@param msg 	 Die auszugebende Nachricht.
 */
static void check(bool isErr, string msg)
{
	if (isErr) {
		perror(msg.c_str());
		exit(EXIT_FAILURE);
	}
}

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

/**
 * 	Nimmt n-Zeichen aus einer Quelldatei und speichert sie in 
 * 	umgekehrter Reihenfolge in einer Zieldatei.
 *
 *	@param src 			Deskritor der Datei, aus welcher Daten gelesen werden.
 *	@param dst 			Deskriptor der Datei, wohin die Daten geschrieben werden.
 *	@param len 			Anzahl der zu lesenden Zeichen.
 *	@param srcOff 		Offset in der Quelldatei/Offset der Speicherseite, 
 *						muss das vielfache von Block-Größe sein. 
 *	@param dstOff 		Offset in der Zieldatei/Offset der Speicherseite, 
 *						muss das vielfache von Block-Größe sein.
 *	@param srcPageOff	Offset in der Quell-Speicherseite.
 *	@param dstPageOff	Offset in der Ziel-Speicherseite.
 */
static void moveReversedData(int src, int dst, int len, 
	size_t srcOff, size_t dstOff, int srcPageOff, int dstPageOff)
{
	int dstMapLen = dstPageOff + len;
	if (dstMapLen > PAGESIZE)
		return;
	
	char* srcPage = (char*) mmap(NULL, PAGESIZE, PROT_READ, MAP_PRIVATE, src, srcOff);
	check(srcPage == MAP_FAILED, "Failed to load source file page");

	char* dstPage = (char*) mmap(NULL, dstMapLen, PROT_READ | PROT_WRITE, MAP_SHARED, dst, dstOff);
	check(dstPage == MAP_FAILED, "Failed to load destination file page");

	for (int i = dstPageOff; i < dstMapLen; i++)
		dstPage[i] = srcPage[srcPageOff - i];

	check(munmap(srcPage, len) < 0, "Failed to unload source file page");
	check(munmap(dstPage, len) < 0, "Failed to unload destination file page");
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
	int remDataLen = dataLen - srcFileOff;
	int srcPageOff = remDataLen - 1;

	size_t dstFileOff = 0;
	int dstPageOff = 0;

	moveReversedData(srcFile, dstFile, remDataLen, srcFileOff, dstFileOff, 
					 srcPageOff, dstPageOff);

	if (srcFileOff == 0) {
		close(srcFile);
		close(dstFile);
		return EXIT_SUCCESS;
	}
	srcFileOff = getPrevPageOff(srcFileOff);
	srcPageOff = PAGESIZE - 1;
	dstPageOff = remDataLen;

	size_t bytesRead = remDataLen;
	while (bytesRead < dataLen) {
		int readSize = (srcPageOff + 1) - dstPageOff;
		moveReversedData(srcFile, dstFile, readSize, srcFileOff, dstFileOff, 
						 srcPageOff, dstPageOff);
		srcPageOff -= readSize;
		dstPageOff += readSize;
		if (srcPageOff < 0) {
			srcFileOff = getPrevPageOff(srcFileOff);			// or substract PAGESIZE
			srcPageOff = PAGESIZE - 1;
		}
		if (dstPageOff == PAGESIZE) {
			dstFileOff += PAGESIZE;
			dstPageOff = 0;
		}
		bytesRead += readSize;
	}
	close(srcFile);
	close(dstFile);
	return EXIT_SUCCESS;
}