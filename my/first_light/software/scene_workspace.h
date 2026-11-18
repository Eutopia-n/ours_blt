#ifndef SCENE_WORKSPACE_H
#define SCENE_WORKSPACE_H
#include "survivor_game.h"

typedef struct {int32_t x,y,w,h,z;uint16_t u,sw;uint8_t back,flip,light;} BookStrip;

/* Animated book turns and the game run in separate loops. The game resets
 * its state on entry, and each book turn rebuilds its strips before use. */
static union {
    BookStrip book_mesh[154];
    SurvivorGame game;
} scene_workspace;
#endif
