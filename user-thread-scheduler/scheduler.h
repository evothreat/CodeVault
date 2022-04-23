#ifndef SCHEDULER_H
#define SCHEDULER_H

#define TASK_STACKSIZE 16 * 1024

typedef void* (*task_func_t)(void*);

typedef struct {
	unsigned int id;
	unsigned int grp_id;
	task_func_t	 func;
	void* 		 arg;
	size_t 		 stack_size;
} task_t;

void yield();
void run_tasks(task_t* tasks, int n);

int get_unique_id();

#endif
