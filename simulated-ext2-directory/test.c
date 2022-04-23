#include "directory-simulation.h"
#include <unistd.h>
#include <fcntl.h>
#include <stdio.h>


int write_simdir_to(FILE* const fd, char* const msg)
{
	int dir = open("directory.sim", O_RDONLY);
	if (dir < 0) return -1;
	fprintf(fd, "\n\n%s\n", msg);
	fprintf(fd, "%s\n", "--------------------------------------------------------------------------------");
	fprintf(fd, "%12s%10s%10s%10s  %s\n", "inode", "rec_len", "name_len", "type", "name");
	fprintf(fd, "%s\n", "--------------------------------------------------------------------------------");
	struct Record rec;
	while (read_record(dir, &rec) > 0) {
		if (rec.inode > 0) {
			fprintf(fd, "%12u%10u%10u%10u  %s\n", rec.inode, rec.rec_len, rec.name_len, rec.type, rec.name);
		}
	}
	return close(dir);
}

int main() {
	// creating directory file
	int dir = open("directory.sim", O_WRONLY | O_CREAT | O_TRUNC, 644);
	if (dir < 0) return -1;
	close(dir);

	FILE* fd = fopen("test.txt", "w");
	// creating files
	sim_creat("fileA.txt");
	write_simdir_to(fd, "creat('fileA.txt')");
	sim_creat("fileA.txt");
	write_simdir_to(fd, "creat('fileA.txt') (exists)");
	sim_creat("fileB.pdf");
	write_simdir_to(fd, "creat('fileB.pdf')");
	sim_creat("fileD.exe");
	write_simdir_to(fd, "creat('fileD.exe')");
	
	// creating dirs
	sim_mkdir("documents");
	write_simdir_to(fd, "mkdir('documents')");
	sim_mkdir("downloads");
	write_simdir_to(fd, "mkdir('downloads')");
	sim_mkdir("pictures");
	write_simdir_to(fd, "mkdir('pictures')");
	sim_mkdir("pictures");
	write_simdir_to(fd, "mkdir('pictures') (exists)");
	sim_mkdir("music");
	write_simdir_to(fd, "mkdir('music')");
	sim_mkdir("videos");
	write_simdir_to(fd, "mkdir('videos')");
	
	// removing dirs
	sim_rmdir("pictures");
	write_simdir_to(fd, "rmdir('pictures')");
	sim_rmdir("documents");
	write_simdir_to(fd, "rmdir('documents')");
	
	// creating hard links
	sim_link("fileA.txt", "link_fileA.txt");
	write_simdir_to(fd, "link('hell_world.txt', 'link_fileA.txt')");

	sim_link("fileB.pdf", "link_fileB.pdf");
	write_simdir_to(fd, "link('fileB.pdf', 'link_fileB.pdf')");
	
	sim_link("not_existing.pdf", "link_not_existing.pdf");
	write_simdir_to(fd, "link('not_existing.pdf', 'link_not_existing.pdf') (not exist)");
	
	sim_link("downloads", "link_downloads");
	write_simdir_to(fd, "link('downloads', 'link_downloads') (directory)");
	
	// symlinks
	sim_creat("fileC.py");
	write_simdir_to(fd, "creat('fileC.py')");
	
	sim_symlink("fileC.py", "link_fileC.py");
	write_simdir_to(fd, "symlink('fileC.py', 'link_fileC.py')");
	
	sim_symlink("videos", "link_videos");
	write_simdir_to(fd, "symlink('videos', 'link_videos')");
	
	// unlinking
	sim_unlink("link_fileA.txt");
	write_simdir_to(fd, "unlink('link_fileA.txt')");
	
	sim_unlink("link_fileB.pdf");
	write_simdir_to(fd, "unlink('link_fileB.pdf')");
	
	sim_unlink("fileD.exe");
	write_simdir_to(fd, "unlink('fileD.exe')");
	
	sim_unlink("link_videos");
	write_simdir_to(fd, "unlink('link_videos')");

	// renaming
	sim_rename("fileA.txt", "file1.txt");
	write_simdir_to(fd, "rename('fileA.txt', 'file1.txt')");

	sim_rename("fileB.pdf", "file2.pdf");
	write_simdir_to(fd, "rename('fileB.pdf', 'file2.pdf')");
	
	sim_rename("videos", "videos_images");
	write_simdir_to(fd, "rename('videos', 'videos_images')");
	return fclose(fd);
}
