#include <unistd.h>
#include <grp.h>
#include <pwd.h>
#include <dirent.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <string>
#include <time.h>
#include <vector>
#include <map>
#include <algorithm>

using namespace std;

const int MAX_PATH_LEN = 256;
const int BLOCK_SIZE = 1024;

struct Dir
{
	DIR 		      *dirp;
	string 			   path;
	unsigned long long size;
};

struct Entry
{
	string 	    name;
	struct stat stat;
};

string getGroupName(const gid_t gid)
{
	return string(getgrgid(gid) -> gr_name);
}

string getOwnerName(const uid_t uid)
{
	return string(getpwuid(uid) -> pw_name);
}

string getModificationTime(const time_t mtime)
{
	char t[32];
	strftime(t, sizeof(t), "%b %2d %H:%M", localtime(&mtime));
	return string(t);
}

string getFileProtection(const mode_t mode)
{
	string p;
	p += (mode & S_IFDIR) ? 'd' : '-';
	p += (mode & S_IRUSR) ? "r" : "-";
    p += (mode & S_IWUSR) ? "w" : "-";
    p += (mode & S_IXUSR) ? "x" : "-";
    p += (mode & S_IRGRP) ? "r" : "-";
    p += (mode & S_IWGRP) ? "w" : "-";
    p += (mode & S_IXGRP) ? "x" : "-";
    p += (mode & S_IROTH) ? "r" : "-";
    p += (mode & S_IWOTH) ? "w" : "-";
    p += (mode & S_IXOTH) ? "x" : "-";
    return p;
}

string getReadableSize(const size_t size, const bool h)
{
	if (!h) {
		return to_string(size);
	}
	const string units[] = {"B", "K", "M", "G", "T"};
	unsigned long long q = size;
	int r = 0;
	int i = 0;
	while (q >= BLOCK_SIZE) {
		r = q % BLOCK_SIZE;
		q /= BLOCK_SIZE;
		i++;
	}
	r = ceil((r / (float) BLOCK_SIZE) * 10);
	return to_string(q) + string(",") + to_string(r) + units[i];
}

string getFilepath(const string dir, const string file)
{
	return dir + string("/") + file;
}

string getCurrentDir()
{
	char cwd[MAX_PATH_LEN];
	getcwd(cwd, sizeof(cwd));		// check for Error?
	return string(cwd);
}

string toLower(string str) 
{
	string lowStr;
	for (char &c : str) {
		if (c >= 'A' && c <= 'Z') {
			lowStr += (c + 32);
		} else {
			lowStr += c;
		}
	}
	return lowStr;
}

void printEntryInfo(const Entry e, const map<char, bool> opts)
{
	if (opts.at('i')) {
			cout << setw(10) << left << e.stat.st_ino;
		}
		if (opts.at('l')) {
			cout << getFileProtection(e.stat.st_mode) 			  << " "
				 << e.stat.st_nlink	 							  << " "
		     	 << getOwnerName(e.stat.st_uid)  				  << " "
		     	 << getGroupName(e.stat.st_gid) 		 		  << " "
		     	 << setw(15) << right 
		     	 << getReadableSize(e.stat.st_size, opts.at('h')) << " "
		     	 << getModificationTime(e.stat.st_mtime) 	 	  << " ";
		}
		cout << e.name << '\n';
}

int ls(const string path, const map<char, bool> opts)
{
	Dir cd;
	if (path.empty()) {
		cd.path = getCurrentDir();
	} else {
		struct stat s;
		if (stat(path.c_str(), &s) == -1) {
			// Datei existiert nicht
			return -1;
		}
		if (S_ISDIR(s.st_mode)) {
			cd.path = path;
		} else {
			Entry e;
			e.name = path;
			e.stat = s;
			printEntryInfo(e, opts);
			return 0;
		}
	}
	cd.dirp = opendir(cd.path.c_str());
	cd.size = 0;
	// alle Dateien und Verzeichnisse werden ausgelesen
	// und in einer Schlange gespeichert
	vector<Entry> entries;
	vector<Entry> dirs;
	for (struct dirent *e = readdir(cd.dirp); e != NULL; e = readdir(cd.dirp)) {
		if (string(e -> d_name).back() == '.') {
			continue;
		}
		Entry entry;
		entry.name = e -> d_name;
		if (stat(getFilepath(cd.path, entry.name).c_str(), &entry.stat) == -1) {
			return -1;
		}
		if (opts.at('R') && S_ISDIR(entry.stat.st_mode)) {
			dirs.push_back(entry);
		}
		cd.size += entry.stat.st_size;
		entries.push_back(entry);
	}
	closedir(cd.dirp);
	if (!opts.at('U')) {
		// sortiere nach den Dateinamen
		sort(entries.begin(), entries.end(), [](Entry e1, Entry e2) {
			return toLower(e1.name) > toLower(e2.name);
		});
	}
	cout << "Dir: "   << cd.path 						<< endl;
	cout << "Total: " << getReadableSize(cd.size, true) << endl;
	while (!entries.empty()) {
		Entry e = entries.back();
		entries.pop_back();
		printEntryInfo(e, opts);
	}
	cout << endl;
	if (opts.at('R')) {
		while (!dirs.empty()) {
			Entry d = dirs.back();
			dirs.pop_back();
			if (ls(getFilepath(cd.path, d.name).c_str(), opts) == -1) {
				return -1;
			}
		}
	}
	return 0;
}

int main()
{
	// falls der jeweilige Parameter angegeben, setze auf True
	map<char, bool> opts = {
		{'l', true},
		{'i', true},
		{'h', true},
		{'U', false},
		{'R', true},
		{'k', false}
	};
	if (ls("", opts) == -1) {
		perror("ERROR");
	}
	return 0;
}