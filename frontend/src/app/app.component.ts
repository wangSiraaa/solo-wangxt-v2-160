import { CommonModule } from '@angular/common';
import { HttpClientModule } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from './api.service';
import {
  Analysis,
  DecisionDetail,
  MissingPolicy,
  Scenario,
  VersionSnapshot,
} from './models';
import { AuditPanelComponent } from './audit-panel.component';
import { NormalizationPanelComponent } from './normalization-panel.component';
import { RawMatrixComponent } from './raw-matrix.component';
import { ReversalPanelComponent } from './reversal-panel.component';
import { ScoringPanelComponent } from './scoring-panel.component';
import {
  WeightChoice,
  WeightsPanelComponent,
} from './weights-panel.component';
import {
  FreezeRequestData,
  VersionPanelComponent,
} from './version-panel.component';
import { VersionViewerComponent } from './version-viewer.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    HttpClientModule,
    RawMatrixComponent,
    AuditPanelComponent,
    NormalizationPanelComponent,
    WeightsPanelComponent,
    ScoringPanelComponent,
    ReversalPanelComponent,
    VersionPanelComponent,
    VersionViewerComponent,
  ],
  template: `
    <header>
      <h1>技术选型 · 多准则决策工作台</h1>
      <p class="subtitle">
        指标方向 · 权重来源 · 每步转换 · 排名逆转 —— 全部摊开给委员会看。
        算法只产出<em>可审计的建议</em>，不产出“客观唯一最佳”。
      </p>
    </header>

    <div class="toolbar panel">
      <label>决策场景
        <select [ngModel]="decisionId" (ngModelChange)="switchDecision($event)">
          <ng-container *ngFor="let s of scenarios">
            <option *ngIf="s.decisions.length" [value]="s.decisions[0].id">
              {{ s.name }}
            </option>
          </ng-container>
        </select>
      </label>
      <label>缺失值策略
        <select [(ngModel)]="missingPolicy" (ngModelChange)="runAnalysis()">
          <option value="neutral">中性 0.5（默认，不奖不罚）</option>
          <option value="row_mean">该行已知项均值</option>
          <option value="exclude_weight">该格不计分，行内权重重归一</option>
        </select>
      </label>
      <button (click)="runAnalysis()">重新计算</button>
      <span class="spinner" *ngIf="loading">计算中…</span>
    </div>

    <p class="scenario-desc" *ngIf="currentScenario">{{ currentScenario.description }}</p>
    <p class="err" *ngIf="error">{{ error }}</p>

    <ng-container *ngIf="decision && analysis">
      <app-raw-matrix
        [criteria]="decision.criteria"
        [alternatives]="decision.alternatives"
        [raw]="analysis.raw_values"
        [notes]="analysis.value_notes">
      </app-raw-matrix>

      <app-audit-panel
        [duplicates]="analysis.audits.duplicates"
        [outliers]="analysis.audits.outliers">
      </app-audit-panel>

      <app-normalization-panel
        [criteria]="decision.criteria"
        [alternatives]="decision.alternatives"
        [matrix]="analysis.models.normalization.matrix"
        [meta]="analysis.models.normalization.meta"
        [warnings]="analysis.models.normalization.warnings"
        [missingCells]="analysis.models.normalization.missing_cells">
      </app-normalization-panel>

      <app-weights-panel
        [criteria]="decision.criteria"
        [weightSets]="decision.weight_sets"
        [analysis]="analysis"
        [(choice)]="weightChoice"
        (changed)="runAnalysis()">
      </app-weights-panel>

      <app-scoring-panel [analysis]="analysis"></app-scoring-panel>
      <app-reversal-panel [analysis]="analysis"></app-reversal-panel>

      <app-version-panel
        [analysis]="analysis"
        [versions]="decision.versions"
        [error]="freezeError"
        (freeze)="freeze($event)"
        (open)="openVersion($event)">
      </app-version-panel>
    </ng-container>

    <app-version-viewer
      [snapshot]="versionSnapshot"
      (close)="versionSnapshot = null">
    </app-version-viewer>

    <footer>
      计算：FastAPI + NumPy/SciPy（WSM、TOPSIS、熵权、CRITIC、MAD 异常检测）；
      存储：PostgreSQL（原始指标/单位/权重来源/决策版；本地可用 SQLite 回退）；
      前端：Angular。任何总分都不能替代委员会对方向、权重与逆转风险的判断。
    </footer>
  `,
})
export class AppComponent implements OnInit {
  scenarios: Scenario[] = [];
  decisionId = 1;
  decision: DecisionDetail | null = null;
  analysis: Analysis | null = null;
  loading = false;
  error = '';
  freezeError = '';
  missingPolicy: MissingPolicy = 'neutral';
  weightChoice: WeightChoice = {
    mode: 'manual',
    weightSetId: null,
    override: {},
  };
  versionSnapshot: VersionSnapshot | null = null;

  constructor(private api: ApiService) {}

  ngOnInit() {
    this.api.scenarios().subscribe((s) => {
      this.scenarios = s;
      if (s.length) this.switchDecision(s[0].decisions[0].id);
    });
  }

  get currentScenario(): Scenario | undefined {
    return this.scenarios.find((x) =>
      x.decisions.some((d) => d.id === this.decisionId)
    );
  }

  switchDecision(id: number) {
    this.decisionId = Number(id);
    this.api.decision(this.decisionId).subscribe((d) => {
      this.decision = d;
      const manual = d.weight_sets.find((w) => w.method === 'manual');
      this.weightChoice = {
        mode: 'manual',
        weightSetId: manual?.id ?? null,
        override: manual ? { ...manual.weights } : {},
      };
      this.runAnalysis();
    });
  }

  private requestBody() {
    const c = this.weightChoice;
    if (c.mode === 'manual') {
      return c.weightSetId !== null
        ? { weight_set_id: c.weightSetId, use_derived: 'manual' as const,
            missing_policy: this.missingPolicy }
        : { weights_override: c.override, use_derived: 'manual' as const,
            missing_policy: this.missingPolicy };
    }
    return {
      weight_set_id: null,
      use_derived: c.mode,
      missing_policy: this.missingPolicy,
    };
  }

  runAnalysis() {
    if (!this.decision) return;
    if (
      this.weightChoice.mode === 'manual' &&
      this.weightChoice.weightSetId === null
    ) {
      const sum = Object.values(this.weightChoice.override).reduce(
        (a, b) => a + (Number(b) || 0),
        0
      );
      if (Math.abs(sum - 1) > 1e-6) {
        this.error = `人工权重之和为 ${sum.toFixed(3)}，需等于 1 才会发起计算。`;
        return;
      }
    }
    this.loading = true;
    this.error = '';
    this.api.analyze(this.decisionId, this.requestBody()).subscribe({
      next: (a) => {
        this.analysis = a;
        this.loading = false;
      },
      error: (e) => {
        this.loading = false;
        this.error = e?.error?.detail
          ? typeof e.error.detail === 'string'
            ? e.error.detail
            : JSON.stringify(e.error.detail)
          : '计算请求失败';
      },
    });
  }

  freeze(data: FreezeRequestData) {
    if (!this.analysis) return;
    this.freezeError = '';
    this.api
      .freeze(this.decisionId, { ...this.requestBody(), ...data })
      .subscribe({
        next: () => {
          this.api.decision(this.decisionId).subscribe((d) => {
            this.decision = d;
          });
        },
        error: (e) => {
          this.freezeError =
            e?.error?.detail ?? '冻结失败，请检查权重与版本说明。';
        },
      });
  }

  openVersion(id: number) {
    this.api.version(id).subscribe((v) => (this.versionSnapshot = v));
  }
}
