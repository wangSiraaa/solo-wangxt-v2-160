import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Analysis, VersionMeta } from './models';

export interface FreezeRequestData {
  label: string;
  method: 'wsm' | 'topsis';
  comment: string;
}

@Component({
  selector: 'app-version-panel',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="panel" *ngIf="analysis">
      <h2>⑥ 冻结“决策版”：算法输出不是最终结论</h2>
      <p class="hint">
        冻结会把原始矩阵、规范化中间值、权重来源、排名与当时的数据体检结果
        原样存入 PostgreSQL 的 <code>decision_versions</code>，之后任何人都能复盘。
      </p>

      <div class="card freeze">
        <div class="row">
          <label>版本说明</label>
          <input [(ngModel)]="label" placeholder="如：技术委员会 10 月评审 · 倾向 WSM">
        </div>
        <div class="row">
          <label>采用模型</label>
          <select [(ngModel)]="method">
            <option value="wsm">WSM 加权和</option>
            <option value="topsis">TOPSIS</option>
          </select>
        </div>
        <div class="row">
          <label>人工备注（为什么相信/不相信这个排序）</label>
          <textarea [(ngModel)]="comment" rows="2"
            placeholder="如：已注意到延迟与 SLA 指标重复，下次会前由架构组合并；磐石报价异常待核实"></textarea>
        </div>
        <button class="primary" (click)="submit()">冻结当前结果为决策版</button>
        <span class="err" *ngIf="error">{{ error }}</span>
      </div>

      <div class="card">
        <h3>历史决策版（{{ versions.length }}）</h3>
        <table>
          <thead>
            <tr><th>#</th><th>说明</th><th>模型</th><th>冻结时间</th><th></th></tr>
          </thead>
          <tbody>
            <tr *ngFor="let v of versions">
              <td>{{ v.id }}</td>
              <td>{{ v.label }}</td>
              <td>{{ v.method | uppercase }}</td>
              <td class="hint">{{ v.created_at | date:'yyyy-MM-dd HH:mm' }}</td>
              <td><button (click)="open.emit(v.id)">查看快照</button></td>
            </tr>
          </tbody>
        </table>
        <p *ngIf="!versions.length" class="hint">尚未冻结任何版本。</p>
      </div>
    </section>
  `,
})
export class VersionPanelComponent {
  @Input() analysis: Analysis | null = null;
  @Input() versions: VersionMeta[] = [];
  @Input() error = '';
  @Output() freeze = new EventEmitter<FreezeRequestData>();
  @Output() open = new EventEmitter<number>();

  label = '';
  method: 'wsm' | 'topsis' = 'wsm';
  comment = '';

  submit() {
    if (!this.label.trim()) {
      this.error = '请先填写版本说明再冻结。';
      return;
    }
    this.error = '';
    this.freeze.emit({
      label: this.label.trim(),
      method: this.method,
      comment: this.comment,
    });
  }
}
