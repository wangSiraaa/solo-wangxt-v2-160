import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Analysis, Criterion, WeightSet } from './models';
import { fmt } from './format';

export interface WeightChoice {
  mode: 'manual' | 'entropy' | 'critic';
  weightSetId: number | null;
  override: Record<string, number>;
}

@Component({
  selector: 'app-weights-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="panel">
      <h2>③ 权重：人工设定与数据推得，严格分开</h2>

      <div class="tabs">
        <button [class.active]="choice.mode === 'manual'"
                (click)="setMode('manual')">人工权重</button>
        <button [class.active]="choice.mode === 'entropy'"
                (click)="setMode('entropy')" title="按列信息量推求">
          熵权（数据推得）
        </button>
        <button [class.active]="choice.mode === 'critic'"
                (click)="setMode('critic')" title="对比强度 × 冲突性">
          CRITIC（数据推得）
        </button>
      </div>

      <!-- Manual -->
      <div *ngIf="choice.mode === 'manual'" class="card">
        <div class="row">
          <label>选择已保存的人工权重集：</label>
          <select [ngModel]="choice.weightSetId"
                  (ngModelChange)="pickSet($event)">
            <option [ngValue]="null">— 页面临时设定（不保存）—</option>
            <option *ngFor="let w of weightSets" [ngValue]="w.id">
              {{ w.name }}
            </option>
          </select>
        </div>

        <table class="wtab">
          <thead>
            <tr><th>指标</th><th>权重</th><th *ngIf="activeSet">来源/依据</th></tr>
          </thead>
          <tbody>
            <tr *ngFor="let c of criteria; let j = index">
              <td>{{ c.label }}</td>
              <td>
                <input type="number" min="0" max="1" step="0.01"
                       [disabled]="choice.weightSetId !== null"
                       [(ngModel)]="choice.override[c.key]"
                       (ngModelChange)="changed.emit()">
              </td>
              <td *ngIf="activeSet" class="hint">
                {{ j === 0 ? activeSet.source : '' }}
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <th>合计</th>
              <th [class.bad]="sumError">{{ manualSum | number:'1.3-3' }}</th>
            </tr>
          </tfoot>
        </table>
        <p class="warn-text" *ngIf="sumError">
          权重之和必须恰好为 1（当前 {{ manualSum | number:'1.3-3' }}），
          否则后端拒绝计算。
        </p>
        <p class="hint" *ngIf="choice.weightSetId === null">
          临时权重不会写入数据库；要作为可追溯依据，必须填写来源后保存。
        </p>
      </div>

      <!-- Derived -->
      <div *ngIf="choice.mode !== 'manual' && analysis" class="card">
        <p class="warn-text">{{ analysis.derived_weights.disclaimer }}</p>
        <table class="wtab">
          <thead><tr><th>指标</th><th>推得权重</th><th>诊断量</th></tr></thead>
          <tbody>
            <tr *ngFor="let c of criteria; let j = index">
              <td>{{ c.label }}</td>
              <td>{{ fmt(derived.weights[j]) }}</td>
              <td class="hint">
                <ng-container *ngIf="choice.mode === 'entropy'">
                  熵 e = {{ fmt(derived.diagnostics['entropy'][j]) }}，
                  1−e = {{ fmt(derived.diagnostics['divergence_1_minus_e'][j]) }}
                </ng-container>
                <ng-container *ngIf="choice.mode === 'critic'">
                  σ = {{ fmt(derived.diagnostics['std'][j]) }}，
                  冲突量 = {{ fmt(derived.diagnostics['conflict'][j]) }}
                </ng-container>
              </td>
            </tr>
          </tbody>
        </table>
        <ul class="warnings" *ngIf="derived.notes.length">
          <li *ngFor="let n of derived.notes">{{ n }}</li>
        </ul>
      </div>

      <div class="card provenance" *ngIf="analysis">
        <h3>本次计算实际使用的权重（可核对）</h3>
        <p>
          来源：<span class="tag" [class]="analysis.weight_provenance.origin">
            {{ provenanceLabel }}
          </span>
          依据：{{ analysis.weight_provenance.source || '（数据推得）' }}
        </p>
        <table class="wtab inline">
          <tr *ngFor="let c of criteria; let j = index">
            <td>{{ c.label }}</td>
            <td>{{ fmt(analysis.weight_vector[j]) }}</td>
          </tr>
          <tr><th>合计</th><th>{{ analysis.weight_sum | number:'1.6-6' }}</th></tr>
        </table>
      </div>
    </section>
  `,
})
export class WeightsPanelComponent {
  @Input() criteria: Criterion[] = [];
  @Input() weightSets: WeightSet[] = [];
  @Input() analysis: Analysis | null = null;
  @Input() choice: WeightChoice = { mode: 'manual', weightSetId: null, override: {} };
  @Output() choiceChange = new EventEmitter<WeightChoice>();
  @Output() changed = new EventEmitter<void>();

  fmt = fmt;

  get activeSet(): WeightSet | undefined {
    return this.weightSets.find((w) => w.id === this.choice.weightSetId);
  }

  get manualSum(): number {
    return Object.values(this.choice.override)
      .reduce((a, b) => a + (Number(b) || 0), 0);
  }

  get sumError(): boolean {
    return this.choice.mode === 'manual'
      && this.choice.weightSetId === null
      && Math.abs(this.manualSum - 1) > 1e-6;
  }

  get derived() {
    return this.choice.mode === 'entropy'
      ? this.analysis!.derived_weights.entropy
      : this.analysis!.derived_weights.critic;
  }

  get provenanceLabel(): string {
    const o = this.analysis?.weight_provenance;
    if (!o) return '';
    return {
      manual: '人工设定（已保存、带来源）',
      manual_adhoc: '人工临时设定（未保存）',
      entropy: '熵权 · 数据推得',
      critic: 'CRITIC · 数据推得',
    }[o.origin];
  }

  setMode(mode: WeightChoice['mode']) {
    this.choice = { ...this.choice, mode };
    this.choiceChange.emit(this.choice);
    this.changed.emit();
  }

  pickSet(id: number | null) {
    this.choice = { ...this.choice, weightSetId: id };
    if (id !== null) {
      const ws = this.activeSet;
      if (ws) this.choice = { ...this.choice, override: { ...ws.weights } };
    }
    this.choiceChange.emit(this.choice);
    this.changed.emit();
  }
}
