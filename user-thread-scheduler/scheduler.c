#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <ucontext.h>
#include <pthread.h>
#include <string.h>
#include "scheduler.h"

#define SCHED_STACKSIZE 16 * 1024
#define MAX_TASKS 32

typedef enum {
	RUNNABLE,
	TERMINATED
} task_state_t;

typedef struct {
	task_t*		 data;
	task_state_t state;
	ucontext_t 	 ctxt;
} running_task_t;

typedef struct {
	ucontext_t 	    ctxt;
	pthread_t       pthread;
	running_task_t* tasks[MAX_TASKS];
	size_t		 	task_count;
	running_task_t* curr_task;	 
} scheduler_t;


int unique_id = 1;

int get_unique_id() 
{
	return unique_id++;
}

//---------------------------
scheduler_t** schedulers;
int	scheduler_n;

//---------------------------
void schedule(scheduler_t* sched)
{
	int active = 1;
	while (active) {
		active = 0;
		for (int i = 0; i < sched->task_count; i++) {
			if (sched->tasks[i]->state == RUNNABLE) {
				sched->curr_task = sched->tasks[i];
				swapcontext(&sched->ctxt, &sched->curr_task->ctxt);
				if (sched->curr_task->state == RUNNABLE) {
					active = 1;
				}
			}
		}
	}
}

scheduler_t* new_scheduler()
{
	scheduler_t* sched = malloc(sizeof(scheduler_t));
	if (sched == NULL) {
		perror("allocating memory for scheduler");
		exit(EXIT_FAILURE);
	}
	sched->task_count = 0;
	sched->curr_task = NULL;
	return sched;
}

void run_scheduler(scheduler_t* sched)
{
	ucontext_t ret_point;
	getcontext(&sched->ctxt);
	sched->ctxt.uc_link = &ret_point;
	sched->ctxt.uc_stack.ss_sp = malloc(SCHED_STACKSIZE);
	sched->ctxt.uc_stack.ss_size = SCHED_STACKSIZE;
	sched->ctxt.uc_stack.ss_flags = 0;
	if (sched->ctxt.uc_stack.ss_sp == NULL) {
		perror("allocating memory for stack");
		exit(EXIT_FAILURE);
	}
	makecontext(&sched->ctxt, (void (*)(void)) schedule, 1, sched);
	swapcontext(&ret_point, &sched->ctxt);
}

void del_scheduler(scheduler_t* sched)
{
	for (int i = 0; i < sched->task_count; i++) {
		if (sched->tasks[i] != NULL) {
			free(sched->tasks[i]->ctxt.uc_stack.ss_sp);
			free(sched->tasks[i]);
		}
	}
	/* Also set NULL in global array*/
	free(sched->ctxt.uc_stack.ss_sp);
	free(sched);
}

void yield()
{
	pthread_t pthread = pthread_self();
	for (int i = 0; i < scheduler_n; i++) {
		if (schedulers[i]->pthread == pthread) {
			swapcontext(&schedulers[i]->curr_task->ctxt, &schedulers[i]->ctxt);
		}
	}
}

void run_task(scheduler_t* sched, task_func_t f, void* arg)
{
	f(arg);
	sched->curr_task->state = TERMINATED;
	yield();
}

void add_task(scheduler_t* sched, task_t* task)
{
	if (sched->task_count + 1 == MAX_TASKS) {
		printf("task limit reached\n");
		exit(EXIT_FAILURE);
	}
	running_task_t* rtask = malloc(sizeof(running_task_t));
	if (rtask == NULL) {
		perror("allocating memory for running task");
		exit(EXIT_FAILURE);
	}
	rtask->data = task;
	rtask->state = RUNNABLE;
	getcontext(&rtask->ctxt);
	rtask->ctxt.uc_link = &sched->ctxt;
	rtask->ctxt.uc_stack.ss_sp = malloc(task->stack_size);
	rtask->ctxt.uc_stack.ss_size = task->stack_size;
	rtask->ctxt.uc_stack.ss_flags = 0;
	if (rtask->ctxt.uc_stack.ss_sp == NULL) {
		perror("allocating memory for running task stack");
		exit(EXIT_FAILURE);
	}
	makecontext(&rtask->ctxt, (void (*)(void)) run_task, 3, sched, task->func, task->arg);
	sched->tasks[sched->task_count] = rtask;
	sched->task_count++;
}

void run_tasks(task_t* tasks, int n)
{
	schedulers = malloc(n * sizeof(scheduler_t*));
	if (schedulers == NULL) {
		perror("allocating memory for schedulers");
		exit(EXIT_FAILURE);
	}
	int grp_n = 0;
	int checked[n];
	memset(checked, 0, n * sizeof(int));
	for (int i = 0; i < n; i++) {
		if (!checked[i]) {
			schedulers[grp_n] = new_scheduler();
			add_task(schedulers[grp_n], &tasks[i]);
			checked[i] = 1;
			for (int j = i + 1; j < n; j++) {
				if (tasks[i].grp_id == tasks[j].grp_id) {
					checked[j] = 1;
					add_task(schedulers[grp_n], &tasks[j]);
				}
			}
			grp_n++;
			scheduler_n++;
		}
	}
	*schedulers = realloc(*schedulers, grp_n * sizeof(scheduler_t*));
	if (schedulers == NULL) {
		perror("reallocating memory for schedulers");
		exit(EXIT_FAILURE);
	}
	for (int i = 0; i < grp_n; i++) {
		pthread_create(&schedulers[i]->pthread, NULL, (void* (*)(void*)) run_scheduler, 
			schedulers[i]);
	}
	for (int i = 0; i < grp_n; i++) {
		pthread_join(schedulers[i]->pthread, NULL);
	}

	for (int i = 0; i < grp_n; i++) {
		del_scheduler(schedulers[i]);
	}
	scheduler_n = 0;
	free(schedulers);
}