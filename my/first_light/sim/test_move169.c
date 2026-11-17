#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "../software/survivor_game.c"
static SurvivorGame g,copy;
static void start(unsigned speed,unsigned dash) {
    game_reset(&g,12345);g.state=GAME_PLAY;g.orbit_count=0;
    g.spawn_wait=g.attack_wait=g.invincible=60000;
    g.speed=(uint16_t)speed;g.dash=(uint8_t)dash;
}
int main(void) {
    const unsigned keys[4]={8,4,2,1},speeds[5]={512,576,640,704,768};
    for(unsigned s=0;s<5;s++)for(unsigned dash=0;dash<2;dash++) {
        int dx[4],dy[4],cx[4],cy[4];
        for(unsigned d=0;d<4;d++) {
            start(speeds[s],dash);int x=g.x,y=g.y,cam_x=game_camera_x(&g),cam_y=game_camera_y(&g);
            for(unsigned t=0;t<60;t++)game_tick(&g,keys[d]);
            dx[d]=g.x-x;dy[d]=g.y-y;cx[d]=game_camera_x(&g)-cam_x;cy[d]=game_camera_y(&g)-cam_y;
        }
        assert(dx[0]==-dx[1] && dy[2]==-dy[3]);
        assert(!dy[0] && !dy[1] && !dx[2] && !dx[3]);
        // Physical equality for 640x480 stretched to 16:9 is 4*dx=3*dy.
        assert(magnitude(4*dx[0]-3*dy[2])<=2);
        assert(magnitude(4*cx[0]-3*cy[2])<=4);
        if(!s && !dash)assert(dx[0]==120*256 && dy[2]==160*256);
        printf("PLAYER speed_q8=%u dash=%u 60ticks x_q8=%d y_q8=%d camera_x=%d camera_y=%d\n",
               speeds[s],dash,dx[0],dy[2],cx[0],cy[2]);
        for(unsigned d=0;d<4;d++) {
            start(speeds[s],dash);int x=g.x,y=g.y;
            game_tick(&g,(d&1u?4u:8u)|(d&2u?1u:2u));
            int ax=magnitude(g.x-x),ay=magnitude(g.y-y);
            assert(magnitude(4*ax-3*ay)<=2);
            // De-stretched diagonal squared distance remains the original
            // normalized magnitude, within two Q8 units of rounding.
            unsigned scalar=(speeds[s]*181u)/256u;if(dash)scalar*=2u;
            assert((unsigned)ax==scalar);
        }
    }
    for(unsigned held=0;held<16;held++) {
        start(512,0);int x=g.x,y=g.y;game_tick(&g,held);
        if((held&3u)==3u || !(held&3u))assert(g.y==y);
        if((held&12u)==12u || !(held&12u))assert(g.x==x);
    }
    for(unsigned kind=0;kind<5;kind++) {
        int delta[4];
        for(unsigned d=0;d<4;d++) {
            start(512,0);int x=g.x/8,y=g.y/8;
            int ex=x+(d<2?(d?-200:200)*32:0),ey=y+(d>=2?(d==3?-200:200)*32:0);
            g.enemies[GAME_MAX_ENEMIES-1u]=(GameEnemy){ex,ey,200,200,(uint8_t)kind,0};
            for(unsigned t=0;t<60;t++)game_tick(&g,0);
            delta[d]=d<2?g.enemies[GAME_MAX_ENEMIES-1u].x-ex:g.enemies[GAME_MAX_ENEMIES-1u].y-ey;
        }
        assert(delta[0]==-delta[1] && delta[2]==-delta[3]);
        assert(4*delta[0]==3*delta[2]);
        printf("ENEMY kind=%u 60ticks x_q5=%d y_q5=%d\n",kind,delta[0],delta[2]);
    }
    const int points[][2]={{0,0},{0,6400},{6400,0},{6400,6400},{-6400,6400},
        {6400,-6400},{-6400,-6400},{1,32768},{65500,1},{999,777},{-12345,6789}};
    for(unsigned p=0;p<sizeof(points)/sizeof(points[0]);p++)for(unsigned t=0;t<3;t++) {
        int vx,vy,dx=points[p][0],dy=points[p][1],speed=44;
        enemy_direction_step(dx,dy,speed,t,&vx,&vy);
        if(!dx && !dy){assert(!vx && !vy);continue;}
        assert((!dx || vx*dx>=0) && (!dy || vy*dy>=0));
        assert(magnitude(vx*dy-vy*dx)<=magnitude(dx)+magnitude(dy));
        assert(magnitude(4*magnitude(vx)+3*magnitude(vy)-4*speed)<7);
    }
    // Three-tick fractions do not leak between frames, pauses or games.
    for(int speed=-768;speed<=768;speed++) {
        int sum=0;for(unsigned t=0;t<3;t++)sum+=motion_vertical_step(speed,t);
        assert(3*sum==speed*4*3);
    }
    start(512,0);g.state=GAME_PAUSED;copy=g;game_tick(&g,2);assert(!memcmp(&g,&copy,sizeof(g)));
    start(512,0);g.y=(GAME_WORLD_Y_MAX-16)*256-1;game_tick(&g,2);
    assert(g.y==(GAME_WORLD_Y_MAX-16)*256);
    start(512,0);g.y=(GAME_WORLD_Y_MIN+16)*256+1;game_tick(&g,1);
    assert(g.y==(GAME_WORLD_Y_MIN+16)*256);
    int vx,vy;direction_step(0,1000,224,&vx,&vy);assert(!vx && vy==224);
    direction_step(1000,0,224,&vx,&vy);assert(vx==224 && !vy);
    puts("MOVE169 TESTS PASSED: player/5 enemy physical axis equality, base/upgraded/dash/diagonal/opposite keys, weighted pursuit heading, exact three-tick fractions, camera/boundary/pause, original projectile direction");
    return 0;
}
