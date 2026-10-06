import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { McdaService } from './mcda.service';
import {
  Candidate, Criterion, Report, ReversalReport, StepTrace, Version,
} from './models';
import { MatrixTableComponent } from './components/matrix-table.component';
import { WeightAuditComponent } from './components/weight-audit.component';
import { RankTableComponent } from './components/rank-table.component';
import { QualityPanelComponent } from './components/quality-panel.component';
import { ReversalPanelComponent } from './components/reversal-panel.component';
import { OptionsPanelComponent, UiOptions } from './components/options-panel.component';

const DEFAULT_OPTS: UiOptions = {
  missing_strategy: 'median',
  clip_outliers: false,
  clip_method: 'mad',
  clip_mad_k: 3,
  weight_basis: 'manual',
  combined_alpha: 0.5,
  keep_constants: false,
  drop_criterion_ids: [],
  drop_candidate_ids: [],
};

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule, MatrixTableComponent, WeightAuditComponent,
    RankTableComponent, QualityPanelComponent, ReversalPanelComponent,
    OptionsPanelComponent,
  ],
  template: `
    <header class="topbar">
      <h1>技术选型委员会 · 多准则分析台（WSM + TOPSIS）</h1>
      <p>
        逐步展示原始指标 → 规范化 → 权重 → 加权 → 理想解距离的全部转换。
        排序是<b>给定口径下的参考</b>，不是客观唯一答案。后端持久化：{{ svc.health() }}
      </p>
    </header>

    <div class="layout">
      <div>
        <app-options-panel
          [opts]="opts"
          [criteria]="criteria"
          [candidates]="candidates"
          [versions]="versions"
          [reversal]="reversal"
          (run)="analyze()"
          (reset)="resetAll()"
          (loadVersion)="loadVersion($event)"
          (runReversal)="runReversal()"
        />
      </div>

      <div>
        <div class="disclaimer">
          <b>委员会须知：</b>一个总分会掩盖方向差异——成本型指标（越小越好）若按收益型处理，
          花钱最多的方案会得最高分。本台对三类指标分别规范化；常量列不自动满分（默认剔除）；
          缺失值按选定策略插补而非送分；人工权重与熵权分两列列出来源。
          改变权重、裁剪异常值、增删候选都可能改变名次，请连同步骤矩阵一起复核。
        </div>

        <ng-container *ngIf="report">
          <app-quality-panel
            [duplicates]="report.duplicate_criteria"
            [outliers]="report.outlier_cells"
            [warnings]="report.warnings"
          />

          <div class="two-col">
            <app-rank-table
              title="加权求和模型 WSM"
              scoreLabel="加权总分"
              [rows]="report.wsm_rank"
              note="WSM：各指标规范化值 × 权重之和。可加性假设强，1 分性能与 1 分成本被视为等值。"
            />
            <app-rank-table
              title="TOPSIS 贴近度"
              scoreLabel="贴近度 C"
              [rows]="report.topsis_rank"
              [showTopsis]="true"
              note="TOPSIS：离正理想解最近、离负理想解最远者优。理想解随当前候选集变化——增删候选可逆转名次。"
            />
          </div>

          <app-weight-audit
            [audit]="report.weight_audit"
            [rawSum]="report.weight_sum_raw"
          />

          <app-matrix-table
            *ngFor="let step of report.steps; let k = index"
            [step]="step"
            [heat]="k >= 2"
            [marks]="k === 1 ? missingMarks() : emptyMarks"
          />

          <div class="panel" *ngIf="report.warnings.length">
            <h2>运行口径备忘</h2>
            <ul class="step-notes">
              <li *ngFor="let w of report.warnings">{{ w }}</li>
            </ul>
          </div>
        </ng-container>

        <app-reversal-panel [report]="reversal" />

        <div class="panel" *ngIf="criteria.length">
          <h2>附录：指标原始定义（PostgreSQL criteria 表）</h2>
          <table>
            <thead>
              <tr>
                <th class="rowhead">代码</th><th class="rowhead">名称</th><th>单位</th>
                <th>方向</th><th>人工权重</th><th style="text-align:left">来源</th><th>目标区间</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let c of criteria">
                <td class="rowhead">{{ c.code }}</td>
                <td class="rowhead">{{ c.name }}</td>
                <td>{{ c.unit || '—' }}</td>
                <td>
                  <span class="chip benefit" *ngIf="c.ctype==='benefit'">收益↑</span>
                  <span class="chip cost" *ngIf="c.ctype==='cost'">成本↓</span>
                  <span class="chip target" *ngIf="c.ctype==='target'">目标区间</span>
                </td>
                <td>{{ c.weight }}</td>
                <td style="text-align:left;white-space:normal;max-width:260px">{{ c.source }}</td>
                <td>{{ c.target_low !== null && c.target_low !== undefined ?
                  '[' + c.target_low + ', ' + c.target_high + ']' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
})
export class AppComponent implements OnInit {
  criteria: Criterion[] = [];
  candidates: Candidate[] = [];
  versions: Version[] = [];
  report: Report | null = null;
  reversal: ReversalReport | null = null;
  opts: UiOptions = { ...DEFAULT_OPTS };

  constructor(public svc: McdaService) {}

  ngOnInit(): void {
    this.svc.getCriteria().subscribe((c) => (this.criteria = c));
    this.svc.getCandidates().subscribe((c) => (this.candidates = c));
    this.svc.getVersions().subscribe((v) => (this.versions = v));
    this.analyze();
  }

  analyze(): void {
    this.svc.analyze(this.body()).subscribe({
      next: (r) => (this.report = r),
      error: (e) => alert('分析失败：' + JSON.stringify(e?.error ?? e)),
    });
  }

  runReversal(): void {
    this.svc.reversal(this.body()).subscribe({
      next: (r) => (this.reversal = r),
      error: (e) => alert('逆转分析失败：' + JSON.stringify(e?.error ?? e)),
    });
  }

  loadVersion(id: number): void {
    this.svc.versionReport(id).subscribe((r) => {
      this.report = r;
      const v = r.version;
      this.opts = {
        missing_strategy: v.missing_strategy ?? 'median',
        clip_outliers: !!v.clip_outliers,
        clip_method: v.clip_method ?? 'mad',
        clip_mad_k: v.clip_mad_k ?? 3,
        weight_basis: v.weight_basis ?? 'manual',
        combined_alpha: v.combined_alpha ?? 0.5,
        keep_constants: !!v.keep_constants,
        drop_criterion_ids: [...(v.drop_criterion_ids ?? [])],
        drop_candidate_ids: [...(v.drop_candidate_ids ?? [])],
      };
    });
  }

  resetAll(): void {
    this.opts = { ...DEFAULT_OPTS, drop_criterion_ids: [], drop_candidate_ids: [] };
    this.reversal = null;
    this.analyze();
  }

  emptyMarks = new Set<string>();

  /** 步骤1中 None 的位置，即步骤2里被插补/裁剪处理的单元格 */
  missingMarks(): Set<string> {
    const s = new Set<string>();
    const raw = this.report?.steps?.[0]?.matrix ?? [];
    raw.forEach((row, i) => row.forEach((v, j) => {
      if (v === null || v === undefined) s.add(`${i},${j}`);
    }));
    return s;
  }

  private body(): Record<string, unknown> {
    return { ...this.opts };
  }
}
