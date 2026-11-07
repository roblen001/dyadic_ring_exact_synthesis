"""Small reusable presentation beats, separate from compiler mathematics."""
from manim import (UP, RIGHT, LEFT, GREEN, GREY_B, YELLOW, Arrow, Create,
                   FadeIn, FadeOut, VGroup, Write)
from dyadic_viz.kinetic_objects import bare_matrix, math_token, caption
from dyadic_viz.kinetic_stage import fit


def summary(context, event):
    p=event['payload']
    before=context.state(p['before_state_id'])
    after=context.state(p['after_state_id'])
    context.clear()
    op_count=len(p['operation_ids'])
    heading=caption(f'{op_count} repeated operations condensed' if op_count else
                    'Repeated column checks condensed',font_size=26).move_to([0,3.5,0])
    same_column=(before['focus'] is not None and after['focus'] is not None
                 and before['focus']['column']==after['focus']['column'])
    unchanged=before['matrix_id']==after['matrix_id']
    if unchanged:
        matrix=context.matrix_for(p['after_state_id'],height=5.3,width=10)
        context.scene.play(FadeIn(heading),FadeIn(matrix),run_time=.7)
        context.add(heading,matrix)
        context.matrix,context.mode=matrix,'matrix'
    else:
        if same_column:
            old=context.colored_vector(context.column(p['before_state_id']),height=4.6)
            new=context.colored_vector(context.column(p['after_state_id']),height=4.6)
            a=math_token(rf'k={before["focus"]["lde"]}',height=.5,color=YELLOW)
            b=math_token(rf'k={after["focus"]["lde"]}',height=.5,color=GREEN)
        else:
            old=context.matrix_for(p['before_state_id'],height=4.5,width=5.5)
            new=context.matrix_for(p['after_state_id'],height=4.5,width=5.5)
            a=math_token(r'U_{\mathrm{before}}',height=.45)
            b=math_token(r'U_{\mathrm{after}}',height=.45)
        old.move_to([-3.7,-.3,0]);new.move_to([3.7,-.3,0])
        a.next_to(old,UP,buff=.3);b.next_to(new,UP,buff=.3)
        arrow=Arrow([-.65,-.3,0],[.65,-.3,0],buff=.04,color=GREY_B)
        context.scene.play(FadeIn(heading),FadeIn(old),Write(a),run_time=.6)
        context.scene.wait(.45)
        context.scene.play(Create(arrow),FadeIn(new),Write(b),run_time=1.1)
        context.add(heading,old,new,a,b,arrow)
        # No stale vector/lift objects survive into subsequent detailed beats.
        context.matrix=None
        context.mode='summary'
    context.state_id=p['after_state_id']
    context.applied=list(event['applied_operation_ids'])


def formula(context, event):
    # Keep the stage intact for the next semantic event; put the formula on a
    # temporary clean slide so it cannot overlap a busy matrix or residue view.
    saved=list(context.scene.mobjects)
    if saved:
        context.scene.play(*[FadeOut(o) for o in saved],run_time=.3)
    equation=fit(math_token(event['payload']['expression'],height=.9),width=13,height=5.5)
    context.scene.play(Write(equation),run_time=.7)
    context.scene.wait(event['narration']['hold_seconds'])
    context.scene.play(FadeOut(equation),run_time=.3)
    if saved:
        context.scene.play(*[FadeIn(o) for o in saved],run_time=.3)


def compact_recovery(context, event):
    """Bounded overview for long circuits; full gate list stays in the trace."""
    context.clear()
    count=len(context.trace['result']['recovered_factors'])
    product=math_token(r'U=G_1^{-1}G_2^{-1}\cdots G_m^{-1}',height=.7).move_to([0,1.5,0])
    size=math_token(rf'm={count}',height=.55,color=YELLOW).move_to([0,2.8,0])
    time=caption('Circuit execution order',font_size=26).move_to([0,-.2,0])
    order=math_token(r'G_m^{-1}\;\longrightarrow\;\cdots\;\longrightarrow\;G_1^{-1}',height=.65).move_to([0,-1.4,0])
    context.scene.play(Write(product),Write(size),run_time=1)
    context.scene.play(FadeIn(time),Write(order),run_time=1.3)
    context.add(product,size,time,order)
    context.mode='recovery'
    context.state_id=context.trace['result']['final_state_id']
