"""Layered, pixel-preserving book animation for the UI art prototype only."""
import math
from PIL import Image, ImageDraw, ImageEnhance


FRAME_COUNT = 121
FRAME_MS = 20


def ease(value):
    """Quintic easing gives zero velocity and acceleration at both ends."""
    t=max(0.0,min(1.0,value))
    return t*t*t*(t*(t*6-15)+10)


def _project_sheet(front,back,hinge,top,width,height,angle,bend=0.0,thick=1):
    """Project a sheet as narrow strips; curvature varies across its width."""
    layer=Image.new('RGBA',(640,480))
    shadow=Image.new('RGBA',(640,480))
    edge=ImageDraw.Draw(layer)
    count=154
    points=[(0.0,0.0)]
    normals=[]
    for n in range(count):
        u=(n+.5)/count
        local=angle+bend*math.sin(math.pi*u)
        x,z=points[-1]
        points.append((x+width/count*math.cos(local),z+width/count*math.sin(local)))
        normals.append(local)

    def project(n):
        x,z=points[n]
        perspective=1.0/(1.0-z/5200.0)
        cy=top+height*.5-z*.025
        return hinge+x*perspective,cy-height*.5*perspective,cy+height*.5*perspective

    outline=[project(n) for n in range(count+1)]
    free_x,free_z=points[-1]
    # Three stepped shadow bands preserve the pixel style while conveying height.
    if abs(math.sin(angle))>.015:
        near=hinge+free_x+free_z*.10
        y0=top+max(4,free_z*.035)
        y1=top+height+max(4,free_z*.065)
        sd=ImageDraw.Draw(shadow)
        for pad,alpha in ((6,12),(3,18),(0,26)):
            sd.polygon([(hinge-2,top+4),(near+pad,y0-pad),
                        (near+pad,y1+pad),(hinge-2,top+height+2)],fill=(10,9,20,alpha))

    cache={}
    # Far strips are painted first, including where a curled leaf folds over itself.
    for n in sorted(range(count),key=lambda n:(points[n][1]+points[n+1][1])):
        x0,t0,b0=outline[n];x1,t1,b1=outline[n+1]
        left=round(min(x0,x1));right=round(max(x0,x1))
        if right<=left:continue
        yy=round((t0+t1)*.5);hh=max(1,round((b0+b1-t0-t1)*.5))
        back_facing=math.cos(normals[n])<0
        source=back if back_facing else front
        # A smaller light change on paper keeps the handwritten details legible.
        light=round((.80+.20*abs(math.cos(normals[n])))*32)/32
        key=(back_facing,light)
        if key not in cache:cache[key]=ImageEnhance.Brightness(source).enhance(light)
        source=cache[key]
        a=round(n/count*source.width);b=max(a+1,round((n+1)/count*source.width))
        strip=source.crop((a,0,b,source.height))
        if x1<x0:strip=strip.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        strip=strip.resize((right-left,hh),Image.Resampling.NEAREST)
        layer.alpha_composite(strip,(left,yy))

    # A narrow fore edge gives the cover weight without adding a rectangle around it.
    x,yt,yb=outline[-1]
    if thick>1 and .025<angle<math.pi-.025:
        edge.line((round(x),round(yt),round(x),round(yb)),fill=(105,82,60,255),width=thick)
        edge.line((round(x)-1,round(yt),round(x)-1,round(yb)),fill=(212,182,127,255))
    return layer,shadow,math.sin(angle)*width


def _clasp():
    """Separate the original brass clasp so it can unlock before the cover moves."""
    im=Image.new('RGBA',(54,40));d=ImageDraw.Draw(im)
    def p(points):return [(2*(x-209),2*(y-111)) for x,y in points]
    d.polygon(p([(213,111),(229,111),(235,115),(235,125),(229,129),(213,129),(209,125),(209,115)]),fill='#111222')
    d.polygon(p([(214,113),(229,113),(233,117),(233,123),(229,127),(214,127),(212,124),(212,116)]),fill='#68503d')
    d.line(p([(214,114),(229,114),(232,117)]),fill='#e4c98b',width=2)
    d.polygon(p([(221,115),(226,120),(221,125),(216,120)]),fill='#1b1c35')
    d.polygon(p([(221,116),(224,120),(221,123),(218,120)]),fill='#9ae2e4')
    return im


def _page_texture(screen,side):
    """Keep the original page illustration while removing the outer binding."""
    mask=Image.new('L',(640,480));d=ImageDraw.Draw(mask)
    points=[(24,36),(80,28),(172,24),(256,32),(314,48),
            (314,432),(256,444),(172,452),(80,448),(24,438)]
    if side=='right':points=[(640-x,y) for x,y in points]
    d.polygon(points,fill=255)
    im=screen.copy();im.putalpha(mask)
    bounds=(14,18,320,480) if side=='left' else (320,18,636,480)
    im=im.crop(bounds)
    return im.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if side=='left' else im


def create_opening_frames(background,closed,unlatched,front_cover,blank_spread,open_spread,book_mask):
    """Unlock, rotate the cover, curl a following leaf, then settle on the menu."""
    board_front=front_cover.crop((174,32,452,428))
    inside_board=blank_spread.copy();inside_board.putalpha(book_mask)
    board_back=inside_board.crop((14,18,320,480)).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    base_right=open_spread.copy();base_right.putalpha(book_mask)
    base_right=base_right.crop((320,18,636,480))
    leaf_front=_page_texture(blank_spread,'right')
    leaf_back=_page_texture(open_spread,'left')
    clasp=_clasp()
    frames=[]
    timing=[]

    for n in range(FRAME_COUNT):
        t=n/(FRAME_COUNT-1)
        if n==0:
            frames.append(closed.copy());timing.append({'frame':n,'cover_deg':0,'leaf_deg':0});continue
        if n==FRAME_COUNT-1:
            frames.append(open_spread.copy());timing.append({'frame':n,'cover_deg':180,'leaf_deg':180});continue
        pose=ease((t-.13)/.74)
        cover_p=ease((t-.12)/.64)
        leaf_p=ease((t-.28)/.62)
        hinge=174+146*ease((t-.19)/.67)
        top=32-14*pose
        cover_angle=math.pi*cover_p
        leaf_angle=math.pi*leaf_p
        # A very small delayed recoil lets the paper lose its energy after landing.
        if t>.90:
            land=(t-.90)/.10
            leaf_angle-=.018*math.sin(math.pi*land)**2
        width=278+28*pose
        height=396+66*pose

        im=background.copy()
        # The back cover and right-hand text block translate as one bound volume.
        body=base_right.resize((round(298+18*pose),round(416+46*pose)),Image.Resampling.NEAREST)
        im.alpha_composite(body,(round(hinge),round(top)))
        board,board_shadow,bz=_project_sheet(board_front,board_back,hinge,top,
                                            width,height,cover_angle,thick=3)
        page,page_shadow,pz=_project_sheet(leaf_front,leaf_back,hinge+1,top,
                                          width,height,leaf_angle,
                                          bend=.38*math.sin(leaf_angle),thick=1)
        # Angle zero is a sheet under the cover. At rest it lies over the inside board.
        layers=[(bz,board_shadow,board),(pz+.1,page_shadow,page)]
        for _,shadow,layer in sorted(layers,key=lambda item:item[0]):
            im=Image.alpha_composite(im,shadow)
            im=Image.alpha_composite(im,layer)
        # Bridge only the nearly identical first pose, preserving the existing idle art.
        blend=ease((t-.12)/.07)
        if blend<1:im=Image.blend(unlatched,im,blend)

        # The loose clasp pivots around the fore edge, then folds behind the binding.
        if t<.30:
            unlock=ease(t/.16)
            a=unlock*math.pi*.63
            cw=max(2,round(abs(math.cos(a))*54))
            stamp=clasp.resize((cw,40),Image.Resampling.NEAREST)
            if math.cos(a)<0:stamp=stamp.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            opacity=1-ease((t-.20)/.10)
            stamp.putalpha(stamp.getchannel('A').point(lambda v:round(v*opacity)))
            anchor=472+max(0,hinge-174)*.3
            xx=round(anchor-cw if math.cos(a)>=0 else anchor)
            arm=Image.new('RGBA',(640,480));ad=ImageDraw.Draw(arm)
            ad.line((round(anchor-3),240,xx+cw//2,238),fill=(104,80,61,round(255*opacity)),width=4)
            ad.line((round(anchor-3),238,xx+cw//2,237),fill=(228,201,139,round(255*opacity)),width=2)
            im=Image.alpha_composite(im,arm)
            im.alpha_composite(stamp,(xx,222-round(3*math.sin(a))))
        if t>.92:
            # The physical layers converge on the exact final raster, including tiny glyphs.
            im=Image.blend(im,open_spread,ease((t-.92)/.08))
        frames.append(im)
        timing.append({'frame':n,'cover_deg':round(math.degrees(cover_angle),3),
                       'leaf_deg':round(math.degrees(leaf_angle),3),'hinge_x':round(hinge,3)})
    return frames,timing
