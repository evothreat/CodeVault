#include <dirent.h>
#include <iostream>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <map>
#include <vector>
#include <string>

using namespace std;

/*
	Check if all chars in string are digits.
	@param str String to verify.
	@return Are all chars in this string digits?
*/
bool isNumber(const string& str)
{
   for(const char& c: str)
      if(!(c >= '0' && c <= '9')) return false;
   return true;
}

/*
	Get common process name from process comm file.
	@param pid Process id of process, from which one the name should be found.
	@return Process name.
*/
string getNameByPid(const int pid) 
{
	string pname;
	ifstream f("/proc/"+to_string(pid)+"/comm");
	if (f.is_open()) {
		getline(f, pname);
		f.close();
	} else {
		cout << "Failed to open comm file: pid=" << pid << endl;
		exit(EXIT_FAILURE);
	}
  return pname;	
}

/*
	Returns a sorted list with ids of all currently running processes.
	@return Sorted list with process ids.
*/
vector<int> getSortedPids() 
{
	DIR* dirp = opendir("/proc/");
	struct dirent* direntp;
	if (dirp == NULL) {
		cout << "Failed to open process directory" << endl;
		exit(EXIT_FAILURE);
	}
	vector<int> pids;
	while ((direntp = readdir(dirp)) != NULL) {
		string nameStr(direntp->d_name);
		if (isNumber(nameStr)) pids.push_back(stoi(nameStr));
	}
	sort(pids.begin(), pids.end());
	closedir(dirp);
	return pids;
}

/*
	Returns all children pids of process sorted.
	@param parentPid Id of parent process.
	@return Sorted children pids.
*/
vector<int> getChildrenPids(const int parentPid) 
{
	DIR* dirp = opendir(("/proc/"+to_string(parentPid)+"/task/").c_str());
	if (dirp == NULL) {
		cout << "Failed to open task directory: pid=" << parentPid << endl;
		exit(EXIT_FAILURE);
	}
	vector<int> childrenPids;
	struct dirent* direntp;
	while ((direntp = readdir(dirp)) != NULL) {
		string tid(direntp->d_name);
		// 'go back' directories
		if (tid == "." || tid == "..") continue;
		string pidsLine;
		ifstream f("/proc/"+to_string(parentPid)+"/task/"+tid+"/children");
		if (f.is_open()) {
			getline(f, pidsLine);
			f.close();
		} else {
			cout << "Failed to open children file: pid=" << parentPid << ",tid=" << tid << endl;
			exit(EXIT_FAILURE);
		}
		// split pids by whitespace
		istringstream iss(pidsLine);
		string pid;
		while (iss >> pid) childrenPids.push_back(stoi(pid));
	}
	closedir(dirp);
	sort(childrenPids.begin(), childrenPids.end());
	return childrenPids;
}

/*
	Walks through all process child-subdirectories and prints their pids and names.
	@param pid Process id of process to begin.
	@param visited Each visited process marks itself to avoid repetition.
	@param depth Depth of current walk.
*/
void tree(const int pid, map<int, bool>& visited, const int depth)
{
	visited[pid] = true;
	cout << string(depth*2, ' ') << pid << " (" << getNameByPid(pid) << ")" << endl;
	for (int cp: getChildrenPids(pid)) tree(cp, visited, depth+1);
}

int main() 
{
	// get ids of all currently running processes
	vector<int> pids = getSortedPids();
	// map to store process status, set true if already visited
	map<int, bool> visited;
	for (const int p: pids) visited[p] = false;
	// begin iteration
	for (const int p: pids) {
		if (visited.at(p)) continue;		
		tree(p, visited, 0);
	}
}
