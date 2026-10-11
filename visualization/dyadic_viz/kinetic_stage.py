"""A continuous, mathematical stage driven only by supplied trace witnesses.

Prose belongs in the accompanying voiceover script.  This scene uses entries,
residue locations, row motion, and exact substitutions to show each operation.
"""
from __future__ import annotations

import math
import numpy as np
from manim import (
    BLACK, BLUE, DOWN, GREEN, GREY_B, LEFT, PI, RIGHT, UP, WHITE, YELLOW,
    Arrow, Circle, Create, Dot, FadeIn, FadeOut, Indicate, LaggedStart,
    Line, ReplacementTransform, Transform, TransformFromCopy, VGroup, Write,
)
from dyadic_viz.kinetic_objects import bare_matrix, bare_vector, dyadic_expr, math_token, row_color, generator_symbol
from dyadic_viz.kinetic_arithmetic import animate_k


def fit(obj, width=12, height=5.6):
    if obj.width > width:
        obj.scale_to_fit_width(width)
    if obj.height > height:
        obj.scale_to_fit_height(height)
    return obj


class KineticContext:
    def __init__(self, scene, trace):
        self.scene, self.trace = scene, trace
        self.operations = {op['id']: op for op in trace['operations']}
        self.state_id = trace['problem']['initial_state_id']
        self.matrix = self.vector = self.lift = None
        self.stage = VGroup()
        self.mode = None
        self.modulus = None
        self.dots, self.integer_tokens = {}, {}
        self.operator = None
        self.applied = []
        self.verification_equation = None

    def begin_event(self, event, number, total):
        self.started = self.scene.time

    def finish_event(self, event):
        # Narration remains an external, optional audio/editing track.  The
        # trace's explicit hold is respected without displaying its paragraphs.
        self.scene.wait(max(0.15, event['narration']['hold_seconds']))

    def clear(self):
        if self.scene.mobjects:
            self.scene.play(*[FadeOut(obj) for obj in list(self.scene.mobjects)], run_time=.45)
        self.stage = VGroup()
        self.matrix = self.vector = self.lift = None
        self.dots, self.integer_tokens = {}, {}
        self.operator = None
        self.mode = None
        self.verification_equation = None

    def add(self, *objects):
        self.stage.add(*objects)
        self.scene.add(self.stage)

    def state(self, state_id=None):
        return self.trace['states'][state_id or self.state_id]

    def values(self, state_id=None):
        return self.trace['matrices'][self.state(state_id)['matrix_id']]

    def column(self, state_id=None):
        state = self.state(state_id)
        col = state['focus']['column']
        return [row[col] for row in self.values(state_id)]

    def colored_vector(self, values, height=5.1):
        vector = fit(bare_vector(values), width=3, height=height)
        for index, item in vector.entries.items():
            item.set_color(row_color(index))
        return vector

    def matrix_for(self, state_id=None, height=5.0, width=6.0):
        matrix = fit(bare_matrix(self.values(state_id), entry_height=.52), width, height)
        for col in self.state(state_id)['completed_columns']:
            for row in matrix.row_ids:
                matrix.entries[row, col].set_color(GREEN)
        return matrix

    def input(self, event):
        self.state_id = event['payload']['state_id']
        matrix = self.matrix_for(height=5.3, width=9).move_to([.7, 0, 0])
        label = math_token('U=', height=.75).next_to(matrix, LEFT, buff=.6)
        self.scene.play(Write(label), Create(matrix.brackets), run_time=.7)
        self.scene.play(LaggedStart(*[FadeIn(entry, shift=.15*UP)
                        for entry in matrix.entries.values()], lag_ratio=.07), run_time=1.6)
        self.add(matrix, label)
        self.matrix, self.mode = matrix, 'matrix'

    def column_start(self, event):
        self.state_id = event['payload']['state_id']
        column = self.state()['focus']['column']
        destination = self.matrix_for(height=4.7, width=6).move_to([-3.25, 0, 0])
        for (row, col), entry in destination.entries.items():
            entry.set_opacity(1 if col == column else .24)
            if col == column:
                entry.set_color(row_color(row))
        if self.matrix is not None and self.mode == 'matrix':
            old = self.matrix
            others = [obj for obj in self.stage if obj is not old]
            self.scene.play(Transform(old, destination), *[FadeOut(o) for o in others], run_time=1)
            self.scene.remove(*self.scene.mobjects)
            self.scene.add(destination)
        else:
            self.clear()
            self.scene.play(FadeIn(destination), run_time=.5)
        self.stage = VGroup(destination)
        vector = self.colored_vector(self.column()).move_to([3.3, 0, 0])
        name = math_token(rf'v_{{{column}}}', height=.65).next_to(vector, UP, buff=.4)
        self.scene.play(Create(vector.brackets), FadeIn(name), run_time=.4)
        self.scene.play(LaggedStart(*[
            TransformFromCopy(destination.entries[row, column], vector.entries[row], path_arc=-PI/5)
            for row in vector.indices], lag_ratio=.12), run_time=1.5)
        self.add(vector, name)
        self.matrix, self.vector, self.mode = destination, vector, 'column'

    def lde_analysis(self, event):
        self.state_id = event['payload']['state_id']
        focus = self.state()['focus']
        if self.vector is None:
            self.clear()
            self.vector = self.colored_vector(self.column()).move_to([-3, 0, 0])
            self.add(self.vector)
        vector = self.vector
        other = [o for o in self.stage if o is not vector]
        self.scene.play(vector.animate.move_to([-3.3, 0, 0]),
                        *[FadeOut(o) for o in other], run_time=.7)
        self.scene.remove(*self.scene.mobjects)
        self.stage = VGroup(vector)
        self.scene.add(self.stage)
        lift = self.colored_vector(focus['scaled_vector']).move_to([3.3, 0, 0])
        equation = math_token(rf'2^{{{focus["lde"]}}}v=w', height=.72).move_to([0, 3.25, 0])
        arrow = Arrow(vector.get_right()+.4*RIGHT, lift.get_left()-.4*RIGHT,
                      buff=.05, color=GREY_B, stroke_width=2)
        factor = math_token(rf'\times 2^{{{focus["lde"]}}}', color=YELLOW, height=.6).next_to(arrow, UP, buff=.3)
        self.scene.play(Write(equation), Create(arrow), FadeIn(factor), Create(lift.brackets), run_time=.65)
        self.scene.play(LaggedStart(*[
            TransformFromCopy(vector.entries[i], lift.entries[i], path_arc=-PI/5)
            for i in vector.indices], lag_ratio=.15), run_time=1.45)
        self.add(lift, equation, arrow, factor)
        self.lift, self.matrix, self.mode = lift, None, 'lift'

    def residue_point(self, residue, slot, count):
        # A residue clock is a literal view of Z/mZ, not a projection of the
        # matrix's ambient vector space. Coincident points are separated slightly.
        angle = PI/2 - 2*PI*residue/self.modulus
        radius = 1.65 + .20 * (slot - (count-1)/2)
        return np.array([1.9 + radius*math.cos(angle), -.25 + radius*math.sin(angle), 0])

    def residue_analysis(self, event):
        self.state_id = event['payload']['state_id']
        modulus = event['payload']['modulus']
        focus = self.state()['focus']
        indices = event['payload']['indices']
        if self.mode == 'residues' and self.modulus == modulus:
            self.scene.play(*[Indicate(self.dots[i], color=row_color(i), scale_factor=1.5)
                             for i in indices if i in self.dots], run_time=.8)
            return
        old_lift = self.lift
        copies = {i: old_lift.entries[i].copy() for i in indices} if old_lift is not None else {}
        self.clear()
        self.modulus = modulus
        clock = Circle(radius=1.65, color=GREY_B, stroke_width=1.5).move_to([1.9, -.25, 0])
        labels = VGroup()
        for residue in range(modulus):
            pos = self.residue_point(residue, 0, 1)
            direction = pos - clock.get_center()
            labels.add(math_token(str(residue), color=GREY_B, height=.48).move_to(pos+.42*direction/1.65))
        title = math_token(rf'w\;(\mathrm{{mod}}\;{modulus})', height=.7).move_to([1.9, 3.25, 0])
        tokens = {}
        for n, i in enumerate(indices):
            token = math_token(dyadic_expr(focus['scaled_vector'][i]), color=row_color(i), height=.7)
            token.move_to([-4.6, (len(indices)-1)*min(.95,5.2/max(1,len(indices)))/2-n*min(.95,5.2/max(1,len(indices))), 0])
            tokens[i] = token
        self.scene.play(Create(clock), FadeIn(labels), Write(title), run_time=.7)
        if copies:
            self.scene.add(*copies.values())
            self.scene.play(*[ReplacementTransform(copies[i], tokens[i], path_arc=PI/6) for i in indices], run_time=.9)
        else:
            self.scene.play(FadeIn(VGroup(*tokens.values())), run_time=.5)
        residues = focus[f'residues_mod{modulus}']
        dots = {}
        for i in indices:
            same = [j for j in indices if residues[j] == residues[i]]
            dot = Dot(self.residue_point(residues[i], same.index(i), len(same)), radius=.10,
                      color=row_color(i))
            dots[i] = dot
        self.scene.play(LaggedStart(*[TransformFromCopy(tokens[i], dots[i], path_arc=-PI/5)
                                     for i in indices], lag_ratio=.2), run_time=1.6)
        self.add(clock, labels, title, *tokens.values(), *dots.values())
        self.integer_tokens, self.dots, self.mode = tokens, dots, 'residues'

    def indices_selected(self, event):
        indices = event['payload']['indices']
        objects = [self.integer_tokens[i] for i in indices if i in self.integer_tokens]
        if not objects and self.vector is not None:
            objects = [self.vector.entries[i] for i in indices if i in self.vector.entries]
        if objects:
            self.scene.play(*[Indicate(obj, color=YELLOW, scale_factor=1.2) for obj in objects], run_time=.9)

    def generator_symbol(self, generator, inverse=False):
        return generator_symbol(generator, inverse)

    def generator_selected(self, event):
        op = self.operations[event['payload']['operation_id']]
        generator = self.trace['generators'][op['generator_id']]
        if self.operator is not None:
            self.scene.play(FadeOut(self.operator), run_time=.2)
            self.stage.remove(self.operator)
        self.operator = math_token(self.generator_symbol(generator), color=YELLOW, height=.7).move_to([-4.6,3.25,0])
        self.scene.play(Write(self.operator), run_time=.65)
        self.add(self.operator)
        targets = [self.integer_tokens[i] for i in generator['indices'] if i in self.integer_tokens]
        if targets:
            self.scene.play(*[Indicate(obj, color=row_color(i), scale_factor=1.25)
                for obj,i in zip(targets,generator['indices'])],run_time=.6)

    def sign(self, op):
        gen = self.trace['generators'][op['generator_id']]
        before, after = self.state(op['before_state_id']), self.state(op['after_state_id'])
        if self.mode != 'residues':
            self.row_operation(op)
            return
        animations = []
        after_residues = after['focus'][f'residues_mod{self.modulus}']
        for i in gen['indices']:
            if i in self.integer_tokens:
                token = self.integer_tokens[i]
                target = math_token(dyadic_expr(after['focus']['scaled_vector'][i]),
                                    color=row_color(i), height=.7).move_to(token)
                animations.append(Transform(token, target, path_arc=PI/2))
        # Every dot gets its supplied new residue position. This also maintains
        # clear spacing when two previously separate residue classes coincide.
        for i, dot in self.dots.items():
            same = [j for j in self.dots if after_residues[j] == after_residues[i]]
            target = dot.copy().move_to(self.residue_point(after_residues[i], same.index(i),len(same)))
            animations.append(Transform(dot, target, path_arc=PI/2 if i in gen['indices'] else 0))
        self.scene.play(*animations, run_time=1.6)
        self.scene.play(*[Indicate(self.integer_tokens[i],color=row_color(i)) for i in gen['indices']
                         if i in self.integer_tokens],run_time=.5)

    def row_operation(self, op):
        self.clear()
        gen = self.trace['generators'][op['generator_id']]
        matrix = self.matrix_for(op['before_state_id'],height=5.2,width=9)
        for (row,col), entry in matrix.entries.items():
            entry.set_color(row_color(row)).set_opacity(1 if row in gen['indices'] else .3)
        name = math_token(self.generator_symbol(gen),color=YELLOW,height=.7).move_to([0,3.3,0])
        self.scene.play(FadeIn(matrix),Write(name),run_time=.65)
        after = self.matrix_for(op['after_state_id'],height=5.2,width=9)
        if gen['kind'] == 'swap':
            a,b = gen['indices']
            # Carry each entire source row to the other row's location.
            rows = {r:VGroup(*[matrix.entries[r,c] for c in matrix.col_ids]) for r in (a,b)}
            self.scene.play(rows[a].animate(path_arc=PI/2).move_to(rows[b].get_center()),
                            rows[b].animate(path_arc=PI/2).move_to(rows[a].get_center()),run_time=1.8)
        else:
            self.scene.play(*[Transform(matrix.entries[r,c],after.entries[r,c].copy().set_color(row_color(r)),path_arc=PI/2)
                             for r in gen['indices'] for c in matrix.col_ids],run_time=1.4)
        self.scene.play(FadeOut(matrix),FadeIn(after),FadeOut(name),run_time=.35)
        self.stage = VGroup(after)
        self.scene.add(self.stage)
        self.matrix,self.mode=after,'matrix'

    def generator_applied(self,event):
        op=self.operations[event['payload']['operation_id']]
        gen=self.trace['generators'][op['generator_id']]
        if gen['kind']=='k':
            self.clear()
            objects,output=animate_k(self.scene,self.trace,op,lambda _:None)
            self.stage,self.vector,self.mode=objects,output,'k'
        elif gen['kind']=='sign':
            self.sign(op)
        else:
            self.row_operation(op)
        self.state_id=op['after_state_id']
        self.applied.append(op['id'])

    def lde_reduced(self,event):
        p=event['payload']
        before,after=self.state(p['before_state_id']),self.state(p['after_state_id'])
        self.state_id=p['after_state_id']
        # Preserve the K output object while the arithmetic scaffolding departs.
        vector=self.vector
        # The K close-up shows its ordered support; restore all supplied
        # coordinates before depicting the whole column's denominator change.
        if vector is not None and len(vector.indices) != self.trace['problem']['dimension']:
            full=self.colored_vector(self.column()).move_to(vector.get_center())
            self.scene.play(ReplacementTransform(vector,full),run_time=.6)
            self.stage.remove(vector)
            self.stage.add(full)
            vector=full
        if vector is not None:
            self.scene.play(*[FadeOut(o) for o in self.stage if o is not vector],
                            vector.animate.move_to([2.8,0,0]),run_time=.8)
            self.scene.remove(*self.scene.mobjects)
            self.stage=VGroup(vector)
            self.scene.add(self.stage)
        else:
            self.clear()
            vector=self.colored_vector(self.column()).move_to([2.8,0,0])
            self.add(vector)
        old=self.colored_vector(self.column(p['before_state_id'])).move_to([-3,0,0])
        arrow=Arrow(old.get_right()+.5*RIGHT,vector.get_left()-.5*RIGHT,color=GREY_B,buff=.05)
        k=math_token(rf'k={before["focus"]["lde"]}',color=YELLOW,height=.7).next_to(old,UP,buff=.45)
        knew=math_token(rf'k={after["focus"]["lde"]}',color=GREEN,height=.7).next_to(vector,UP,buff=.45)
        self.scene.play(FadeIn(old),Create(arrow),Write(k),run_time=.7)
        self.scene.play(TransformFromCopy(k,knew,path_arc=-PI/4),run_time=1.1)
        self.scene.play(Indicate(vector,color=GREEN,scale_factor=1.12),run_time=.7)
        self.add(old,arrow,k,knew)
        self.vector,self.mode=vector,'reduced'

    def column_integral(self,event):
        self.state_id=event['payload']['state_id']
        column=self.state()['focus']['column']
        self.clear()
        matrix=self.matrix_for(height=5.1,width=8)
        for (row,col),entry in matrix.entries.items():
            if col==column:
                entry.set_color(row_color(row))
        label=math_token(rf'k_{{{column}}}=0',color=YELLOW,height=.65).move_to([0,3.4,0])
        self.scene.play(FadeIn(matrix),Write(label),run_time=.7)
        self.add(matrix,label)
        self.matrix,self.mode=matrix,'matrix'

    def column_complete(self,event):
        self.state_id=event['payload']['state_id']
        col=event['payload']['column']
        destination=self.matrix_for(height=5.1,width=8).move_to([-1,0,0])
        if self.vector is not None:
            vector=self.vector
            self.scene.play(*[FadeOut(o) for o in self.stage if o is not vector],
                            vector.animate.move_to([4.4,0,0]),run_time=.6)
            self.scene.play(FadeIn(destination.brackets),run_time=.25)
            passive=VGroup(*[e for (r,c),e in destination.entries.items() if c!=col])
            self.scene.play(FadeIn(passive),run_time=.35)
            self.scene.play(LaggedStart(*[
                TransformFromCopy(vector.entries[r],destination.entries[r,col],path_arc=PI/5)
                for r in vector.indices],lag_ratio=.1),run_time=1.2)
            self.scene.play(FadeOut(vector),destination.animate.move_to([.4,0,0]),run_time=.6)
        else:
            self.clear()
            self.scene.play(FadeIn(destination),run_time=.5)
        self.scene.remove(*self.scene.mobjects)
        self.stage=VGroup(destination)
        self.scene.add(self.stage)
        completed=VGroup(*[destination.entries[r,col] for r in destination.row_ids])
        self.scene.play(Indicate(completed,color=GREEN,scale_factor=1.08),run_time=.7)
        self.matrix,self.vector,self.mode=destination,None,'matrix'

    def recovery(self,event):
        self.clear()
        factors=self.trace['result']['recovered_factors']
        lhs=math_token('U=',height=.72)
        words=[math_token(self.generator_symbol(self.trace['generators'][f['generator_id']],f['inverse']),
                          color=row_color(i),height=.66) for i,f in enumerate(factors)]
        if not words:
            words=[math_token('I',color=GREEN,height=.75)]
        word=fit(VGroup(lhs,*words).arrange(RIGHT,buff=.3),width=13,height=1.2).move_to([0,2.5,0])
        self.scene.play(Write(lhs),run_time=.4)
        self.scene.play(LaggedStart(*[Write(w) for w in words],lag_ratio=.3),run_time=1.4)
        self.add(word)
        gates=self.trace['result']['circuit']['gates']
        n=self.trace['problem']['dimension']
        spacing=min(.75,4.6/max(1,n))
        ys=[1.1-i*spacing for i in range(n)]
        wires=VGroup(*[Line([-6,y,0],[6.4,y,0],color=GREY_B,stroke_width=1.2) for y in ys])
        labels=VGroup(*[math_token(rf'e_{{{i}}}',height=min(.38,spacing*.55)).move_to([-6.7,y,0]) for i,y in enumerate(ys)])
        direction=Arrow([-5.6,-3.45,0],[5.6,-3.45,0],color=GREY_B,stroke_width=1.4,buff=0)
        time=math_token('t',height=.4).next_to(direction,RIGHT,buff=.2)
        self.scene.play(Create(wires),FadeIn(labels),Create(direction),FadeIn(time),run_time=.9)
        self.add(wires,labels,direction,time)
        for number,gate in enumerate(gates):
            gen=self.trace['generators'][gate['generator_id']]
            x=-4.8+9.6*(number+.5)/max(1,len(gates))
            support=gen['indices']
            line=Line([x,ys[min(support)],0],[x,ys[max(support)],0],color=YELLOW,stroke_width=2)
            dots=VGroup(*[Dot([x,ys[i],0],radius=.065,color=YELLOW) for i in support])
            label=fit(math_token(self.generator_symbol(gen,gate['inverse']),height=.42),
                      width=9.6/max(1,len(gates))*.9,height=.42).move_to([x,1.75,0])
            if factors:
                self.scene.play(TransformFromCopy(words[len(words)-1-number],label,path_arc=PI/4),
                                Create(line),FadeIn(dots),run_time=.8)
            self.add(label,line,dots)
        self.mode='recovery'

    def verification(self,event):
        check=next(c for c in self.trace['verifications'] if c['id']==event['payload']['verification_id'])
        if self.mode=='recovery' and check['kind']!='reconstruction':
            expression=(r'U^{T}U=I' if check['kind']=='input_orthogonality'
                        else r'G_m\cdots G_1U=I')
            equation=math_token(expression,color=GREEN,height=.55).move_to([0,-2.75,0])
            if self.verification_equation is not None:
                self.scene.play(ReplacementTransform(self.verification_equation,equation),run_time=.7)
                self.stage.remove(self.verification_equation)
            else:
                self.scene.play(Write(equation),run_time=.9)
            self.add(equation)
            self.verification_equation=equation
            return
        if check['kind']=='input_orthogonality':
            equation=math_token(r'U^{T}U=I',height=.62).move_to([0,-3.4,0])
            self.scene.play(Write(equation),run_time=1)
            self.add(equation)
        elif check['kind']=='reduction_identity':
            eq=math_token('=I',color=GREEN,height=.75).move_to([5.2,0,0])
            self.scene.play(Write(eq),run_time=.8)
            self.add(eq)
        else:
            equation=math_token(r'U_{\mathrm{original}}=U_{\mathrm{synthesized}}',color=GREEN,height=.55).move_to([0,-2.75,0])
            if self.verification_equation is not None:
                self.scene.play(ReplacementTransform(self.verification_equation,equation),run_time=.9)
                self.stage.remove(self.verification_equation)
            else:
                self.scene.play(Write(equation),run_time=.9)
            self.add(equation)
            self.verification_equation=equation

    def complete(self,event):
        self.scene.wait(.6)


HANDLERS={name:getattr(KineticContext,name) for name in (
    'input','column_start','lde_analysis','residue_analysis','indices_selected',
    'generator_selected','generator_applied','lde_reduced','column_integral','column_complete',
    'recovery','verification','complete')}
HANDLERS['sign_correction']=KineticContext.generator_applied
