import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Candidate, Criterion, ReversalReport } from '../models';

export interface UiOptions {
  missing_strategy: 'median' | 'mean' | 'worst';
  clip_outliers: boolean;
  clip_method: 'percentile' | 'mad';
  clip_mad_k: number;
  weight_basis: 'manual' | 'entropy' | 'combined';
  combined_alpha: number;
  keep_constants: boolean;
  drop_criterion_ids: number[];
  drop_candidate_ids: number[];
}

@Component({
  selector: 'app-options-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="panel">
      <h2>计算情景</h2>

      <h3>缺失值处理</h3>
      <label class="opt">
        <select [(ngModel)]="opts.missing_strategy">
          <option value="median">中位数插补（默认，抗异常）</option>
          <option value="mean">均值插补</option>
          <option value="worst">最差值 0（绝不给满分）</option>
        </select>
      </label>

      <h3>极端异常值</h3>
      <label class="opt"><input type="checkbox" [(ngModel)]="opts.clip_outliers"> 显式裁剪（MAD / 百分位），不静默改数</label>
      <label class="opt" *ngIf="opts.clip_outliers">
        口径
        <select [(ngModel)]="opts.clip_method">
          <option value="mad">MAD 稳健口径</option>
          <option value="percentile">P5–P95 百分位</option>
        </select>
        k=<input type="number" style="width:64px" [(ngModel)]="opts.clip_mad_k" step="0.5">
      </label>

      <h3>权重口径</h3>
      <label class="opt"><input type="radio" name="wb" value="manual" [(ngModel)]="opts.weight_basis"> 纯人工权重</label>
      <label class="opt"><input type="radio" name="wb" value="entropy" [(ngModel)]="opts.weight_basis"> 纯熵权（数据推得）</label>
      <label class="opt"><input type="radio" name="wb" value="combined" [(ngModel)]="opts.weight_basis"> 人工 × 熵权组合</label>
      <label class="opt" *ngIf="opts.weight_basis === 'combined'">
        人工占比 α=<input type="number" style="width:72px" [(ngModel)]="opts.combined_alpha" min="0" max="1" step="0.1">
        （熵权占 {{ (1 - opts.combined_alpha) | number:'1.1-1' }}）
      </label>

      <h3>常量列</h3>
      <label class="opt"><input type="checkbox" [(ngModel)]="opts.keep_constants"> 保留常量列（规范化恒为 0.5，而非满分 1）</label>

      <h3>移出指标（模拟剔除重复指标）</h3>
      <label class="opt" *ngFor="let c of criteria">
        <input type="checkbox" [value]="c.id"
               [checked]="opts.drop_criterion_ids.includes(c.id)"
               (change)="toggleNum(opts.drop_criterion_ids, c.id, $event)">
        <span class="chip" [class.benefit]="c.ctype==='benefit'"
              [class.cost]="c.ctype==='cost'" [class.target]="c.ctype==='target'">{{ typeLabel(c.ctype) }}</span>
        {{ c.code }}
      </label>

      <h3>移出候选（模拟候选增删）</h3>
      <label class="opt" *ngFor="let c of candidates">
        <input type="checkbox" [value]="c.id"
               [checked]="opts.drop_candidate_ids.includes(c.id)"
               (change)="toggleNum(opts.drop_candidate_ids, c.id, $event)">
        {{ c.code }} · {{ c.name }}
      </label>

      <div style="margin-top:12px;display:flex;gap:8px">
        <button (click)="run.emit()">重新计算</button>
        <button class="ghost" (click)="reset.emit()">重置</button>
      </div>
    </div>

    <div class="panel">
      <h2>决策版本（PostgreSQL 快照）</h2>
      <p class="muted">版本保存原始数据快照与全部选项，可复算；下方点击直接载入。</p>
      <label class="opt" *ngFor="let v of versions">
        <button class="ghost" style="padding:2px 10px" (click)="loadVersion.emit(v.id)">载入</button>
        <span>{{ v.label }}</span>
      </label>
      <p class="muted" *ngIf="!versions.length">无已保存版本</p>
    </div>

    <div class="panel">
      <h2>排名逆转实验</h2>
      <p class="muted">用左侧"移出候选"的勾选作为删除集合（不选则默认删当前第一名），对比完整集合。</p>
      <button (click)="runReversal.emit()">运行逆转对比</button>
      <div class="warnbox blue" *ngIf="hasShift" style="margin-top:8px">
        检测到排名位移：分数的参照系随候选集合变化，结论不是唯一客观答案。
      </div>
    </div>
  `,
})
export class OptionsPanelComponent {
  @Input() opts!: UiOptions;
  @Input() criteria: Criterion[] = [];
  @Input() candidates: Candidate[] = [];
  @Input() versions: { id: number; label: string }[] = [];
  @Input() reversal: ReversalReport | null = null;
  @Output() run = new EventEmitter<void>();
  @Output() reset = new EventEmitter<void>();
  @Output() loadVersion = new EventEmitter<number>();
  @Output() runReversal = new EventEmitter<void>();

  toggleNum(list: number[], id: number, ev: Event): void {
    const checked = (ev.target as HTMLInputElement).checked;
    const i = list.indexOf(id);
    if (checked && i === -1) list.push(id);
    if (!checked && i >= 0) list.splice(i, 1);
  }

  typeLabel(t: string): string {
    return { benefit: '收益', cost: '成本', target: '区间' }[t] ?? t;
  }

  get hasShift(): boolean {
    return !!this.reversal?.rows?.some((r) => r.shift !== 0);
  }
}
