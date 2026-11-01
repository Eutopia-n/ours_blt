/* Fixed-point FPGA adaptation of the survivor loop described in
 * migalvalm/vampire-survivors-clone (MIT): timed waves, nearest-target attack,
 * experience thresholds and a paused upgrade choice. Source snapshots and
 * MIT notice are preserved in third_party/survivors_reference.
 */
#include "survivor_game.h"

static int32_t magnitude(int32_t v) { return v<0 ? -v : v; }
static int32_t clamp(int32_t v,int32_t lo,int32_t hi) { return v<lo ? lo : v>hi ? hi : v; }
int32_t game_camera_x(const SurvivorGame *g) {
    int32_t camera=g->x/256-312;
    int32_t maximum=GAME_WORLD_WIDTH-(GAME_X_MAX-GAME_X_MIN);
    if(camera<0) camera=0;
    if(camera>maximum) camera=maximum;
    return camera;
}
int32_t game_camera_y(const SurvivorGame *g) {
    int32_t camera=g->y/256-180;
    int32_t maximum=GAME_WORLD_HEIGHT-(GAME_Y_MAX-GAME_Y_MIN);
    if(camera<0) camera=0;
    if(camera>maximum) camera=maximum;
    return camera;
}
static uint32_t random_next(SurvivorGame *g) {
    uint32_t v=g->rng; v^=v<<13; v^=v>>17; v^=v<<5; g->rng=v; return v;
}
static int overlap(int32_t ax,int32_t ay,int32_t bx,int32_t by,int32_t radius) {
    return magnitude(ax-bx)<radius && magnitude(ay-by)<radius;
}
static void direction_step(int32_t dx,int32_t dy,int32_t speed,int32_t *vx,int32_t *vy) {
    int32_t norm=magnitude(dx)+magnitude(dy);
    *vx=norm ? dx*speed/norm : 0; *vy=norm ? dy*speed/norm : 0;
}
static int32_t motion_vertical_step(int32_t speed,uint32_t ticks) {
    // Diffuse the fractional Q8/Q5 unit across three ticks, with no state.
    // Equal 3-tick distances are exact for every constant speed and sign.
    int32_t value=magnitude(speed);
    int32_t step=(value*(int32_t)GAME_MOTION_Y_NUM+
                  (int32_t)(ticks%GAME_MOTION_Y_DEN))/(int32_t)GAME_MOTION_Y_DEN;
    return speed<0 ? -step : step;
}
static void enemy_direction_step(int32_t dx,int32_t dy,int32_t speed,
                                 uint32_t ticks,int32_t *vx,int32_t *vy) {
    if(!dx) {
        *vx=0;*vy=dy ? motion_vertical_step(dy<0 ? -speed:speed,ticks):0;
        return;
    }
    // Weight the target displacement by the displayed pixel aspect. Both
    // components share a denominator, so tracking still points at the player.
    // The projectile direction_step remains the existing unmodified rule.
    int32_t norm=magnitude(dx)*(int32_t)GAME_MOTION_Y_NUM+
                 magnitude(dy)*(int32_t)GAME_MOTION_Y_DEN;
    *vx=dx*speed*(int32_t)GAME_MOTION_Y_NUM/norm;
    *vy=dy*speed*(int32_t)GAME_MOTION_Y_NUM/norm;
}
static void recount(SurvivorGame *g) {
    g->enemy_count=g->bolt_count=g->gem_count=0;
    for(uint32_t i=0;i<GAME_MAX_ENEMIES;++i) if(g->enemies[i].hp) g->enemy_count++;
    for(uint32_t i=0;i<GAME_MAX_BOLTS;++i) if(g->bolts[i].life) g->bolt_count++;
    for(uint32_t i=0;i<GAME_MAX_GEMS;++i) if(g->gems[i].value) g->gem_count++;
    // Hysteresis keeps the spawn rate stable around the 512-object load threshold.
    uint32_t load=(uint32_t)g->enemy_count+g->bolt_count;
    if(!g->spawn_slow && load>=GAME_SPAWN_SLOW_ENTER) {
        g->spawn_slow=1;
        uint32_t wait=((uint32_t)g->spawn_wait+1u)*GAME_SPAWN_SLOW_FACTOR-1u;
        g->spawn_wait=(uint16_t)(wait>65535u ? 65535u : wait);
    } else if(g->spawn_slow && load<=GAME_SPAWN_SLOW_EXIT) {
        g->spawn_slow=0;
        g->spawn_wait=(uint16_t)(g->spawn_wait/GAME_SPAWN_SLOW_FACTOR);
    }
    if(g->enemy_count>g->peak_enemies) g->peak_enemies=g->enemy_count;
    uint32_t sprites=1u+g->enemy_count+g->bolt_count+g->gem_count+g->orbit_count;
    if(sprites>g->peak_sprites) g->peak_sprites=(uint16_t)sprites;
}
void game_reset(SurvivorGame *g,uint32_t seed) {
    unsigned char *p=(unsigned char *)g;
    for(uint32_t i=0;i<sizeof(*g);++i) p[i]=0;
    g->rng=seed ? seed : 0x6d2b79f5u;
    g->x=(GAME_WORLD_WIDTH/2)*256; g->y=(GAME_WORLD_HEIGHT/2)*256; g->hp=g->max_hp=100;
    /* A larger first threshold prevents a single nearby gem from opening the
     * upgrade screen immediately; the threshold grows with each level below. */
    g->level=1; g->xp_target=GAME_INITIAL_XP_TARGET; g->speed=512; g->damage=2;
    g->attack_period=24; g->magnet=48; g->orbit_count=1; g->peak_sprites=2; g->state=GAME_READY;
}
const char *game_upgrade_name(uint32_t n) {
    static const char *const names[]={"奥术强化","快速施法","冰霜法环","迅捷战靴","宝石磁力","治疗符文"};
    return names[n%6];
}
const char *game_upgrade_detail(uint32_t n) {
    static const char *const details[]={"伤害+1 / 3级穿透 / 上限+2","更快 / 上限2发","法环更多 / 上限冰霜","速度+ / 上限冲刺","范围+ / 上限全图","生命上限+ / 3级再生"};
    return details[n%6];
}
uint32_t game_upgrade_max(uint32_t n) {
    static const uint8_t maximum[]={5,5,4,5,5,3};
    return maximum[n%6];
}
uint32_t game_upgrade_icon(uint32_t n) {
    static const uint8_t icons[]={20,22,21,2,19,23};
    return icons[n%6];
}
static uint32_t next_upgrade(const SurvivorGame *g,uint32_t start) {
    for(uint32_t i=0;i<6;++i) {
        uint32_t n=(start+i)%6;
        if(g->upgrade_level[n]<game_upgrade_max(n)) return n;
    }
    return start%6;
}
static void upgrade(SurvivorGame *g) {
    uint32_t skill=g->options[g->choice],level=g->upgrade_level[skill];
    if(level>=game_upgrade_max(skill)) { g->state=GAME_PLAY; return; }
    level++; g->upgrade_level[skill]=(uint8_t)level;
    switch(skill) {
    case UPGRADE_POWER:
        g->damage++;
        if(level==3) g->bolt_pierce=1;
        if(level==5) { g->bolt_pierce=2; g->damage+=2; }
        break;
    case UPGRADE_RATE:
        if(g->attack_period>8) g->attack_period-=2;
        if(level>=3 && g->attack_period>6) g->attack_period-=2;
        if(level==5 && g->attack_period>4) g->attack_period--;
        if(level==5) g->rapid_burst=1;
        break;
    case UPGRADE_ORBIT:
        if(g->orbit_count<GAME_MAX_ORBITS) g->orbit_count++; else if(g->damage<30) g->damage++;
        if(level>=3) g->orbit_damage=1;
        if(level==4) g->orbit_damage=2;
        break;
    case UPGRADE_SPEED:
        if(g->speed<896) g->speed+=64;
        if(level==5) g->dash=1;
        break;
    case UPGRADE_MAGNET:
        if(g->magnet<192) g->magnet+=24;
        if(level==5) { g->magnet=240; g->magnet_all=1; }
        break;
    default:
        g->max_hp=(uint16_t)clamp(g->max_hp+(level>=2 ? 20 : 10),0,240);
        g->hp=(uint16_t)clamp(g->hp+30+(int32_t)level*5,0,g->max_hp);
        if(level==3) g->regeneration=1;
        break;
    }
    g->state=GAME_PLAY;
}
void game_input(SurvivorGame *g,uint32_t held,uint32_t pressed) {
    (void)held;
    if(g->state==GAME_READY) { if(pressed&16u) g->state=GAME_PLAY; else if(pressed&4u) g->state=GAME_EXIT; return; }
    if(g->state==GAME_OVER || g->state==GAME_WON) {
        if(pressed&16u) { uint32_t seed=g->rng; game_reset(g,seed); g->state=GAME_PLAY; }
        else if(pressed&4u) g->state=GAME_EXIT;
        return;
    }
    if(g->state==GAME_PAUSED) {
        if(pressed&16u) g->state=g->resume_state;
        else if(pressed&4u) g->state=GAME_EXIT;
        return;
    }
    if(g->state==GAME_UPGRADE) {
        if(pressed==1) g->choice=(g->choice+2)%3;
        if(pressed==2) g->choice=(g->choice+1)%3;
        if(pressed==16) upgrade(g);
        if(pressed==8) { g->resume_state=GAME_UPGRADE; g->state=GAME_PAUSED; }
        return;
    }
    // The fifth external key is a dedicated action key, so gameplay pause is
    // deterministic and does not depend on holding a movement chord.
    if(g->state==GAME_PLAY && (pressed&16u)) {
        g->resume_state=GAME_PLAY; g->state=GAME_PAUSED;
    }
}
static void spawn_enemy(SurvivorGame *g,uint32_t wave) {
    for(uint32_t i=0;i<GAME_MAX_ENEMIES;++i) if(!g->enemies[i].hp) {
        GameEnemy *e=&g->enemies[i]; uint32_t v=random_next(g);
        int32_t player_x=g->x/256,player_y=g->y/256;
        int32_t x=clamp(player_x-288+32+(int32_t)((v>>2)%576u),GAME_WORLD_X_MIN,GAME_WORLD_X_MAX);
        int32_t y=clamp(player_y-148+32+(int32_t)((v>>13)%296u),GAME_WORLD_Y_MIN,GAME_WORLD_Y_MAX);
        switch(v&3u) {
        case 0: x=clamp(player_x-288,GAME_WORLD_X_MIN,GAME_WORLD_X_MAX); break;
        case 1: x=clamp(player_x+288,GAME_WORLD_X_MIN,GAME_WORLD_X_MAX); break;
        case 2: y=clamp(player_y-148,GAME_WORLD_Y_MIN,GAME_WORLD_Y_MAX); break;
        default: y=clamp(player_y+148,GAME_WORLD_Y_MIN,GAME_WORLD_Y_MAX); break;
        }
        // Keep a safe entry distance even when the player stands at a wall.
        if(overlap(x,y,g->x/256,g->y/256,80)) {
            x=g->x/256<GAME_WORLD_WIDTH/2 ? GAME_WORLD_X_MAX-16 : GAME_WORLD_X_MIN+16;
            y=g->y/256<GAME_WORLD_HEIGHT/2 ? GAME_WORLD_Y_MAX-16 : GAME_WORLD_Y_MIN+16;
        }
        e->x=x*32; e->y=y*32; // Enemy centres use Q5 world coordinates.
        e->kind=(wave>=8 && (v&15u)==0) ? 4 : wave>=4 ? (uint8_t)((v>>8)%4) : wave>=3 ? (uint8_t)((v>>8)%3) : wave>=1 ? (uint8_t)((v>>8)%2) : 0;
        e->max_hp=(uint8_t)(e->kind==4 ? 20+wave : e->kind==3 ? 8+wave : e->kind==1 ? 5+wave/2 : 2+wave/3);
        e->hp=e->max_hp; e->flash=0;
        g->enemy_steer[i][0]=g->enemy_steer[i][1]=0;
        g->spawned++; return;
    }
}
static void drop_gem(SurvivorGame *g,const GameEnemy *e) {
    uint32_t value=e->kind==4 ? 10 : e->kind==3 ? 5 : e->kind==1 ? 3 : 1;
    uint8_t kind=(uint8_t)((e->kind==1 || e->kind>=3) && (random_next(g)&3u)==0);
    for(uint32_t i=0;i<GAME_MAX_GEMS;++i) if(!g->gems[i].value) {
        g->gems[i].x=e->x/32; g->gems[i].y=e->y/32; g->gems[i].value=(uint16_t)value;
        g->gems[i].kind=kind; return;
    }
    // A full pool merges XP into the nearest gem; no kill reward is discarded.
    uint32_t best=0; int32_t distance=1000000;
    for(uint32_t i=0;i<GAME_MAX_GEMS;++i) {
        int32_t d=magnitude(g->gems[i].x-e->x/32)+magnitude(g->gems[i].y-e->y/32);
        if(d<distance) { best=i; distance=d; }
    }
        g->gems[best].value=(uint16_t)clamp(g->gems[best].value+(int32_t)value,0,60000);
    g->gems[best].kind|=kind;
}
static void hurt_enemy(SurvivorGame *g,GameEnemy *e,uint32_t damage) {
    if(damage>=e->hp) { drop_gem(g,e); e->hp=0; e->flash=0; g->kills++; }
    else { e->hp-=(uint8_t)damage; e->flash=90; }
}
void game_orbit_position(const SurvivorGame *g,uint32_t index,int32_t *x,int32_t *y) {
    // Sixteen positions around a circle; interpolation keeps motion continuous.
    static const int8_t ring[16][2]={{64,0},{59,24},{45,45},{24,59},{0,64},{-24,59},{-45,45},{-59,24},
                                  {-64,0},{-59,-24},{-45,-45},{-24,-59},{0,-64},{24,-59},{45,-45},{59,-24}};
    uint32_t phase=(g->ticks+index*128/(g->orbit_count ? g->orbit_count : 1))&127u;
    uint32_t n=phase/8,next=(n+1)&15u,t=phase&7u;
    *x=g->x/256+(ring[n][0]*(int32_t)(8-t)+ring[next][0]*(int32_t)t)/8;
    *y=g->y/256+(ring[n][1]*(int32_t)(8-t)+ring[next][1]*(int32_t)t)/8;
}
static void shoot(SurvivorGame *g,int32_t spread) {
    int32_t best_distance=200000000; GameEnemy *target=0;
    for(uint32_t i=0;i<GAME_MAX_ENEMIES;++i) if(g->enemies[i].hp) {
        int32_t dx=g->enemies[i].x/32-g->x/256,dy=g->enemies[i].y/32-g->y/256;
        int32_t d=dx*dx+dy*dy;
        if(d<best_distance) { target=&g->enemies[i]; best_distance=d; }
    }
    if(!target) return;
    for(uint32_t i=0;i<GAME_MAX_BOLTS;++i) if(!g->bolts[i].life) {
        GameBolt *b=&g->bolts[i]; int32_t vx,vy;
        direction_step(target->x/32-g->x/256,target->y/32-g->y/256,224,&vx,&vy);
        if(!vx && !vy) vx=224;
        int32_t base_vx=vx,base_vy=vy;
        vx=base_vx-base_vy*spread/224;
        vy=base_vy+base_vx*spread/224;
        b->x=g->x/8; b->y=g->y/8;
        b->vx=vx; b->vy=vy; b->life=90; b->damage=(uint8_t)g->damage; b->pierce=g->bolt_pierce;
        g->shots++; return;
    }
}
/* Soft body separation. The 32-pixel grid is in world space, independent of
 * camera/visibility. Only occupied heads are cleared; at most 16 candidates
 * are inspected per selected enemy, including the worst coincident crowd.
 * Four interleaved groups recompute steering at 15 Hz. Cached small steering
 * steps are applied at 60 Hz, keeping chase/contact and visual motion smooth.
 * Scratch is shared and fully rebuilt/cleared on every call, not game state.
 * Keep these arrays off the 4 KiB stack. No heap, sqrt or pairwise full scan.
 */
#define ENEMY_GRID_COLS ((GAME_WORLD_WIDTH+31)/32)
#define ENEMY_GRID_ROWS ((GAME_WORLD_HEIGHT+31)/32)
#define ENEMY_NEIGHBOR_BUDGET 16u
#define ENEMY_BODY_SPACING (20*32)
#define ENEMY_PUSH_LIMIT 32
static uint16_t enemy_cell_heads[ENEMY_GRID_COLS*ENEMY_GRID_ROWS];
static uint16_t enemy_cell_next[GAME_MAX_ENEMIES],enemy_used_cells[GAME_MAX_ENEMIES];
static uint32_t enemy_body_group(uint32_t kind) {
    // Slimes separate only from slimes; bats only from bats. B/D/E share
    // the original solid group. Cross-group pairs pass through each other.
    return kind==0u ? 0u : kind==2u ? 1u : 2u;
}
static void separate_enemies(SurvivorGame *g) {
    static const int8_t offsets[8][2]={{-1,0},{-1,-1},{0,-1},{1,-1},{1,0},{1,1},{0,1},{-1,1}};
    // Reuse the same scratch for three independent body groups. The bound
    // is still 16 compatible candidates per selected enemy, not 16 per group.
    for(uint32_t body_group=0;body_group<3u;++body_group) {
        uint32_t start=(g->ticks*13u)%GAME_MAX_ENEMIES;
        uint32_t used=0;
        for(uint32_t n=0;n<GAME_MAX_ENEMIES;++n) {
            uint32_t i=(start+n)%GAME_MAX_ENEMIES;
            if(!g->enemies[i].hp || enemy_body_group(g->enemies[i].kind)!=body_group) continue;
            const GameEnemy *e=&g->enemies[i];
            int32_t cx=clamp(e->x/1024,0,ENEMY_GRID_COLS-1);
            int32_t cy=clamp(e->y/1024,0,ENEMY_GRID_ROWS-1);
            uint32_t cell=(uint32_t)(cy*ENEMY_GRID_COLS+cx);
            if(!enemy_cell_heads[cell]) enemy_used_cells[used++]=(uint16_t)cell;
            enemy_cell_next[i]=enemy_cell_heads[cell];
            enemy_cell_heads[cell]=(uint16_t)(i+1u);
        }
        uint32_t group=g->ticks&3u;
        for(uint32_t i=group;i<GAME_MAX_ENEMIES;i+=4u) if(g->enemies[i].hp && enemy_body_group(g->enemies[i].kind)==body_group) {
            const GameEnemy *e=&g->enemies[i];
            int32_t cx=clamp(e->x/1024,0,ENEMY_GRID_COLS-1);
            int32_t cy=clamp(e->y/1024,0,ENEMY_GRID_ROWS-1),fx=0,fy=0;
            uint32_t checked=0;
            // Own cell first; rotate other cells/list insertion to avoid starving
            // one side of a dense cell boundary when the work budget is exhausted.
            for(uint32_t k=0;k<9u && checked<ENEMY_NEIGHBOR_BUDGET;++k) {
                uint32_t side=(k-1u+g->ticks+i)&7u;
                int32_t x=cx+(k ? offsets[side][0] : 0);
                int32_t y=cy+(k ? offsets[side][1] : 0);
                if(x<0 || y<0 || x>=ENEMY_GRID_COLS || y>=ENEMY_GRID_ROWS) continue;
                uint32_t link=enemy_cell_heads[y*ENEMY_GRID_COLS+x];
                while(link && checked<ENEMY_NEIGHBOR_BUDGET) {
                    uint32_t j=link-1u; link=enemy_cell_next[j];
                    if(j==i) continue;
                    ++checked;
                    int32_t dx=e->x-g->enemies[j].x,dy=e->y-g->enemies[j].y;
                    int32_t ax=magnitude(dx),ay=magnitude(dy);
                    if(ax>=ENEMY_BODY_SPACING || ay>=ENEMY_BODY_SPACING) continue;
                    int32_t push=(ENEMY_BODY_SPACING-(ax>ay ? ax : ay)+7)/8;
                    if(push>ENEMY_PUSH_LIMIT) push=ENEMY_PUSH_LIMIT;
                    if(!ax && !ay) {
                        // Equal centres need a deterministic, antisymmetric escape
                        // direction. It does not consume the spawn/drop RNG.
                        uint32_t lo=i<j ? i : j,hi=i<j ? j : i;
                        uint32_t axis=(lo*13u+hi*7u)&3u;
                        int32_t sign=i<j ? 1 : -1;
                        if(axis&2u) sign=-sign;
                        if(axis&1u) fx+=sign*push; else fy+=sign*push;
                    } else if(ax>ay || (ax==ay && ((i^j)&1u))) fx+=dx<0 ? -push : push;
                    else fy+=dy<0 ? -push : push;
                }
            }
            g->enemy_steer[i][0]=(int8_t)clamp(fx,-ENEMY_PUSH_LIMIT,ENEMY_PUSH_LIMIT);
            g->enemy_steer[i][1]=(int8_t)clamp(fy,-ENEMY_PUSH_LIMIT,ENEMY_PUSH_LIMIT);
        }
        for(uint32_t i=0;i<used;++i) enemy_cell_heads[enemy_used_cells[i]]=0;
    }
    // Apply together: the grid and force calculations all see one snapshot.
    for(uint32_t i=0;i<GAME_MAX_ENEMIES;++i) if(g->enemies[i].hp) {
        GameEnemy *e=&g->enemies[i];
        e->x=clamp(e->x+g->enemy_steer[i][0],GAME_WORLD_X_MIN*32,GAME_WORLD_X_MAX*32);
        e->y=clamp(e->y+g->enemy_steer[i][1],GAME_WORLD_Y_MIN*32,GAME_WORLD_Y_MAX*32);
    }
}
/* Reuse the now-cleared separation scratch after all enemy motion. Reverse
 * insertion produces ascending slot lists. A bolt's integer-pixel collision
 * box is +/-15 (the existing strict <16 rule), spanning at most 2x2 32px cells.
 * Merge those lists in ascending slot order so first-hit/pierce/drop RNG match
 * the former full scan exactly. There is no candidate cap or camera culling.
 */
#if GAME_WORLD_X_MIN < 15 || GAME_WORLD_Y_MIN < 15 || \
    GAME_WORLD_X_MAX > GAME_WORLD_WIDTH-15 || GAME_WORLD_Y_MAX > GAME_WORLD_HEIGHT-15
#error "Bolt query needs the existing 15-pixel world inset"
#endif
static uint32_t bolt_grid_build(const SurvivorGame *g) {
    uint32_t used=0;
    for(uint32_t i=GAME_MAX_ENEMIES;i-- >0;) if(g->enemies[i].hp) {
        const GameEnemy *e=&g->enemies[i];
        // separate_enemies has clamped every live centre to the world bounds.
        uint32_t cell=((uint32_t)e->y/1024u)*ENEMY_GRID_COLS+(uint32_t)e->x/1024u;
        if(!enemy_cell_heads[cell]) enemy_used_cells[used++]=(uint16_t)cell;
        enemy_cell_next[i]=enemy_cell_heads[cell];
        enemy_cell_heads[cell]=(uint16_t)(i+1u);
    }
    return used;
}
static void bolt_grid_hit(SurvivorGame *g,GameBolt *b) {
    // A live bolt has already passed the existing world-boundary checks.
    int32_t x=b->x/32,y=b->y/32;
    uint32_t first_x=(uint32_t)(x-15)/32u,last_x=(uint32_t)(x+15)/32u;
    uint32_t first_y=(uint32_t)(y-15)/32u,last_y=(uint32_t)(y+15)/32u;
    uint16_t links[4],previous[4],cells[4];uint32_t count=0;
    for(uint32_t cy=first_y;cy<=last_y;++cy) for(uint32_t cx=first_x;cx<=last_x;++cx) {
        uint32_t cell=cy*ENEMY_GRID_COLS+cx;
        if(enemy_cell_heads[cell]) {
            cells[count]=(uint16_t)cell;links[count]=enemy_cell_heads[cell];previous[count]=0;
            ++count;
        }
    }
    while(b->life) {
        uint32_t link=GAME_MAX_ENEMIES+1u,slot=0;
        for(uint32_t i=0;i<count;++i) if(links[i] && links[i]<link) {link=links[i];slot=i;}
        if(link>GAME_MAX_ENEMIES) break;
        uint32_t index=link-1u,next=enemy_cell_next[index];
        links[slot]=(uint16_t)next;
        GameEnemy *e=&g->enemies[index];
        if(e->hp && overlap(x,y,e->x/32,e->y/32,16)) {
            hurt_enemy(g,e,b->damage);
            if(b->pierce) b->pierce--;else b->life=0;
        }
        // Retire killed nodes so later bolts avoid scanning a dead crowd.
        if(!e->hp) {
            if(previous[slot]) enemy_cell_next[previous[slot]-1u]=(uint16_t)next;
            else enemy_cell_heads[cells[slot]]=(uint16_t)next;
        } else previous[slot]=(uint16_t)link;
    }
}
void game_tick(SurvivorGame *g,uint32_t held) {
    if(g->state!=GAME_PLAY) return;
    g->ticks++; uint32_t wave=g->ticks/(15u*60u);
    int32_t dx=((held&8u)!=0)-((held&4u)!=0),dy=((held&2u)!=0)-((held&1u)!=0);
    int32_t speed=(dx && dy) ? g->speed*181/256 : g->speed;
    if(g->dash && (g->ticks%180u)<12u) speed*=2;
    g->x=clamp(g->x+dx*speed,(GAME_WORLD_X_MIN+16)*256,(GAME_WORLD_X_MAX-16)*256);
    g->y=clamp(g->y+dy*motion_vertical_step(speed,g->ticks),(GAME_WORLD_Y_MIN+16)*256,(GAME_WORLD_Y_MAX-16)*256);
    g->moving=(uint8_t)(dx || dy);
    if(dx) g->direction=dx<0 ? 1 : 2; else if(dy) g->direction=dy<0 ? 3 : 0;
    g->walk_frame=g->moving ? (uint8_t)((g->ticks/8)%4) : 0;
    if(g->invincible) g->invincible--;
    if(g->regeneration && (g->ticks%60u)==0 && g->hp<g->max_hp) g->hp++;
    if(g->spawn_wait) g->spawn_wait--;
    else {
        uint32_t count=2+wave/2;
        for(uint32_t i=0;i<count;++i) spawn_enemy(g,wave);
        uint32_t interval=(wave<10 ? 51u-wave*4u : 11u);
        if(g->spawn_slow)interval*=GAME_SPAWN_SLOW_FACTOR;
        g->spawn_wait=(uint16_t)(interval-1u);
    }
    if(g->attack_wait) g->attack_wait--;
    else {
        if(g->rapid_burst) { shoot(g,-48); shoot(g,48); }
        else shoot(g,0);
        g->attack_wait=g->attack_period;
    }
    for(uint32_t i=0;i<GAME_MAX_ENEMIES;++i) if(g->enemies[i].hp) {
        GameEnemy *e=&g->enemies[i]; int32_t vx,vy;
        int32_t speed_q5=e->kind==4 ? 10 : e->kind==3 ? 15 : e->kind==2 ? 44 : e->kind==1 ? 20 : 28;
        enemy_direction_step(g->x/8-e->x,g->y/8-e->y,speed_q5+(int32_t)wave,g->ticks,&vx,&vy);
        e->x+=vx; e->y+=vy;
        if(e->flash) e->flash--;
        if(overlap(e->x/32,e->y/32,g->x/256,g->y/256,18) && !g->invincible) {
            uint16_t loss=e->kind==4 ? 18 : (e->kind==1 || e->kind==3) ? 12 : 8;
            g->hp=g->hp>loss ? g->hp-loss : 0; g->damage_taken+=loss;
            g->invincible=GAME_INVINCIBLE_TICKS;
        }
        if((g->ticks%15)==0) for(uint32_t n=0;n<g->orbit_count;++n) {
            int32_t x,y; game_orbit_position(g,n,&x,&y);
            if(e->hp && overlap(e->x/32,e->y/32,x,y,20)) hurt_enemy(g,e,1+g->damage/2+g->orbit_damage);
        }
    }
    separate_enemies(g);
    uint32_t bolt_grid_used=0,bolt_grid_ready=0;
    for(uint32_t i=0;i<GAME_MAX_BOLTS;++i) if(g->bolts[i].life) {
        GameBolt *b=&g->bolts[i]; b->x+=b->vx; b->y+=b->vy; b->life--;
        if(b->x<32*GAME_WORLD_X_MIN || b->x>=32*GAME_WORLD_X_MAX || b->y<32*GAME_WORLD_Y_MIN || b->y>=32*GAME_WORLD_Y_MAX) b->life=0;
        if(!b->life) continue;
        // Build lazily: no extra grid work when every bolt is empty/expired.
        if(!bolt_grid_ready) {bolt_grid_used=bolt_grid_build(g);bolt_grid_ready=1;}
        bolt_grid_hit(g,b);
    }
    // No scratch survives a tick, including interleaved independent games.
    for(uint32_t i=0;i<bolt_grid_used;++i) enemy_cell_heads[enemy_used_cells[i]]=0;
    for(uint32_t i=0;i<GAME_MAX_GEMS;++i) if(g->gems[i].value) {
        GameGem *gem=&g->gems[i]; int32_t gdx=g->x/256-gem->x,gdy=g->y/256-gem->y;
        if(g->magnet_all || magnitude(gdx)+magnitude(gdy)<g->magnet) {
            gem->x+=clamp(gdx,-5,5); gem->y+=clamp(gdy,-5,5);
        }
        if(overlap(gem->x,gem->y,g->x/256,g->y/256,16)) {
            g->xp=(uint16_t)clamp(g->xp+gem->value,0,60000);
            if(gem->kind && g->hp) g->hp=(uint16_t)clamp(g->hp+25,0,g->max_hp);
            gem->value=0; g->pickups++;
        }
    }
    // Death takes precedence over victory and upgrades on the same simulation tick.
    if(!g->hp) g->state=GAME_OVER;
    else if(g->ticks>=GAME_DURATION_TICKS) g->state=GAME_WON;
    else if(g->xp>=g->xp_target) {
        g->xp-=g->xp_target; g->level++;
        /* Increase the cost faster than the old fixed +5 schedule. This keeps
         * later waves from producing an upgrade on every small movement. */
        g->xp_target=(uint16_t)clamp((int32_t)g->xp_target+8+(int32_t)g->level*2,20,1000);
        for(uint32_t i=0;i<3;++i) g->options[i]=(uint8_t)next_upgrade(g,(g->level*2+i)%6);
        g->choice=0; g->state=GAME_UPGRADE;
    }
    recount(g);
}
uint32_t game_sprite_count(const SurvivorGame *g) {
    return 1u+g->enemy_count+g->bolt_count+g->gem_count+g->orbit_count;
}
