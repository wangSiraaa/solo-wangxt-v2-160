import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { Analysis } from './models';
import { fmt, rankBadge } from './format';

@Component({
  selector: 'app-scoring-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel" *ngIf="analysis">
      <h2>④ 第二步转换：两个模型分别怎么算</h2>

      <div class="grid two">
        <!-- WSM -->
        <div class="card">
          <h3>加权和模型 WSM</h3>
          <code>总分 = Σ(权重 × 规范化值)</code>
          <p class="hint">每一项“贡献”都摊开：总分就是各格贡献之和，可逐格核对。</p>
          <div class="table-wrap">
            <table class="sticky">
              <thead>
                <tr>
                  <th>排名</th><th>方案</th>
                  <th *ngFor="let c of analysis.criteria">{{ c.label }} 贡献</th>
                  <th>总分</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let a of ordered('wsm'); let i = index">
                  <td class="rank">{{ rankBadge(analysis.models.wsm.ranks[a.i]) }}</td>
                  <td class="alt">{{ a.label }}</td>
                  <td *ngFor="let c of analysis.criteria; let j = index"
                      [class.neg]="contrib('wsm', a.i, j) === 0">
                    {{ fmt(contrib('wsm', a.i, j)) }}
                  </td>
                  <th>{{ fmt(analysis.models.wsm.scores[a.i]) }}</th>
                </tr>
              </tbody>
            </table>
          </div>
          <ul class="warnings" *ngIf="analysis.models.wsm.warnings.length">
            <li *ngFor="let w of analysis.models.wsm.warnings">{{ w }}</li>
          </ul>
        </div>

        <!-- TOPSIS -->
        <div class="card">
          <h3>TOPSIS（逼近理想解）</h3>
          <code>C = D⁻ / (D⁺ + D⁻)</code>
          <p class="hint">
            D⁺ 到理想解的距离、D⁻ 到反理想解的距离；先向量归一再加权。
          </p>
          <div class="table-wrap">
            <table class="sticky">
              <thead>
                <tr><th>排名</th><th>方案</th><th>D⁺</th><th>D⁻</th><th>C</th></tr>
              </thead>
              <tbody>
                <tr *ngFor="let a of ordered('topsis')">
                  <td class="rank">{{ rankBadge(analysis.models.topsis.ranks[a.i]) }}</td>
                  <td class="alt">{{ a.label }}</td>
                  <td>{{ fmt(steps('topsis')['distance_to_best'][a.i]) }}</td>
                  <td>{{ fmt(steps('topsis')['distance_to_worst'][a.i]) }}</td>
                  <th>{{ fmt(analysis.models.topsis.scores[a.i]) }}</th>
                </tr>
              </tbody>
            </table>
          </div>
          <details>
            <summary>查看理想解 / 反理想解与向量归一矩阵</summary>
            <p class="hint">
              理想解：{{ steps('topsis')['ideal_best'] | json }}<br>
              反理想解：{{ steps('topsis')['ideal_worst'] | json }}
            </p>
          </details>
          <ul class="warnings" *ngIf="analysis.models.topsis.warnings.length">
            <li *ngFor="let w of analysis.models.topsis.warnings">{{ w }}</li>
          </ul>
        </div>
      </div>

      <div class="card disagreement"
           *ngIf="ranksDiffer">
        <h3>两个模型排名不一致 —— 这不是计算错误</h3>
        <table>
          <thead><tr><th>方案</th><th>WSM 名次</th><th>TOPSIS 名次</th></tr></thead>
          <tbody>
            <tr *ngFor="let a of analysis.alternatives; let i = index">
              <td class="alt">{{ a.label }}</td>
              <td>{{ analysis.models.wsm.ranks[i] }}</td>
              <td [class.diff]="analysis.models.wsm.ranks[i] !== analysis.models.topsis.ranks[i]">
                {{ analysis.models.topsis.ranks[i] }}
              </td>
            </tr>
          </tbody>
        </table>
        <p class="warn-text">
          WSM 只看加权总分，TOPSIS 还看“离谁更近”。没有任何一个数字能自称
          “客观唯一的最佳”；差异本身就是需要委员会讨论的信息。
        </p>
      </div>
    </section>
  `,
})
export class ScoringPanelComponent {
  @Input() analysis: Analysis | null = null;

  fmt = fmt;
  rankBadge = rankBadge;

  ordered(model: 'wsm' | 'topsis') {
    const a = this.analysis!;
    return a.alternatives
      .map((alt, i) => ({ i, label: alt.label }))
      .sort((x, y) => a.models[model].ranks[x.i] - a.models[model].ranks[y.i]);
  }

  contrib(model: 'wsm' | 'topsis', i: number, j: number): number {
    const m = this.steps(model)['weighted_matrix'] as number[][];
    return m[i][j];
  }

  steps(model: 'wsm' | 'topsis'): Record<string, any> {
    return this.analysis!.models[model].steps as Record<string, any>;
  }

  get ranksDiffer(): boolean {
    const a = this.analysis!;
    return a.alternatives.some(
      (_, i) => a.models.wsm.ranks[i] !== a.models.topsis.ranks[i]
    );
  }
}
