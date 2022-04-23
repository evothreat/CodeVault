/*
 * list.h
 *
 *  Created on: Apr 30, 2018
 *      Author: bs2
 */

#ifndef LIST_H_
#define LIST_H_

#include "string.h"

// @note Some compilers have the offsetof macro available
// as a built-in function. 
#define offsetof(st, m) \
    ((size_t)&(((st *)0)->m))

/**
 * container_of - cast a member of a structure out to the containing structure
 * @param ptr     the pointer to the member.
 * @param type    the type of the container struct this is embedded in.
 * @param member  the name of the member within the struct.
 *
 */
#define container_of(ptr, type, member) \
   ((type*)((char*)ptr - offsetof(type, member)))

struct list_head {
   struct list_head* next;
   struct list_head* prev;
};

/**
 * Adds an element to the end of a doubly linked ring list.
 *
 * @param lh    Pointer to the list head to add to.
 * @param el    Pointer to the list element to add.
 */
#define list_add(lh, el)    \
   (el)->next = (lh);       \
   (el)->prev = (lh)->prev; \
   (lh)->prev->next = (el); \
   (lh)->prev = (el);

/**
 * Removes an element from a doubly linked ring list.
 * WARNING: Does not check whether el->next/prev are NULL.
 * WARNING: Does not work from within loops. See list_rm_loopsafe() below.
 *
 * @param el    The list element to remove.
 */
#define list_rm(el)               \
   (el)->prev->next = (el)->next; \
   (el)->next->prev = (el)->prev; \
   (el)->next = NULL;             \
   (el)->prev = NULL;

/**
 * Removes an element from a doubly linked ring list within a loop. This makes
 * it safe to execute within a loop by assigning el->prev to el after removing
 * el.
 * WARNING: This will overwrite (el) with (el)->prev!
 *
 * @param el    The list element to remove.
 */
#define list_rm_loopsafe(el)               \
   struct list_head* lh_loop = (el)->prev; \
   (el)->prev->next = (el)->next;          \
   (el)->next->prev = (el)->prev;          \
   (el)->next = NULL;                      \
   (el)->prev = NULL;                      \
   (el) = lh_loop;

/**
 * Checks whether a list is empty.
 *
 * @param lh    The list head of the list to check.
 * @return      True if list is empty, false otherwise.
 */
#define list_is_empty(lh) ((lh)->next == (lh))

#define LIST_HEAD_INIT(name) \
   { &(name), &(name) }

#define INIT_HEAD(headptr) \
        (headptr)->next = (headptr); \
        (headptr)->prev = (headptr);

#endif /* LIST_H_ */
