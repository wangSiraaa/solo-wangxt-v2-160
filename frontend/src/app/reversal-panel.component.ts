import { CommonModule } from '@angular/common';
import { Component, Input } from '@angular/core';
import { Analysis } from './models';

@Component({
  selector: 'app-reversal-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel" *ngIf="analysis">
      <h2>⑤ 排名为什么会逆转：逐个删除候选重算</h2>
      <p class="hint">{{ analysis.rank_reversal.explanation }}</p>

      <div class="grid two">
        <div class="card" [class.warn]="dyn.length">
          <h3>动态锚点（默认 min/max + TOPSIS 重定理想解）</h3>
          <p class="hint">
            每删一个候选，端点和理想解都由剩下的人重新决定——幸存者的顺序可能变。
          </p>
          <ul class="reversals">
            <li *ngFor="let r of dyn">
              删除 <strong>{{ label(r.removed) }}</strong> 后，
              <span class="tag">{{ r.model | uppercase }}</span>：
              <span class="order">{{ r.order_before.join(' › ') }}</span>
              →
              <span class="order bad">{{ r.order_after.join(' › ') }}</span>
            </li>
          </ul>
          <p *ngIf="!dyn.length" class="ok-text">该配置下删除任何候选都不改变幸存者顺序。</p>
        </div>

        <div class="card" [class.warn]="fixed.length">
          <h3>固定锚点（外部参照区间，WSM 对此免疫）</h3>
          <p class="hint">
            规范化分母固定为全集/外部锚点，任何人离开都不会重新缩放其他人。
          </p>
          <ul class="reversals">
            <li *ngFor="let r of fixed">
              删除 <strong>{{ label(r.removed) }}</strong> 后
              <span class="tag">{{ r.model | uppercase }}</span> 仍发生逆转：
              {{ r.order_before.join(' › ') }} →
              <span class="bad">{{ r.order_after.join(' › ') }}</span>
            </li>
          </ul>
          <p *ngIf="!fixed.length" class="ok-text">
            固定锚点下两种模型都未因增删候选而逆转（若 TOPSIS 仍逆转，
            说明根源在其理想解随集合变化）。
          </p>
        </div>
      </div>

      <div class="card">
        <h3>把“删除”反过来读就是“新增”</h3>
        <p class="hint">
          上面每条 “删除 X 后 A、B 互换” 都等价于 “向不含 X 的集合新增 X 后
          A、B 互换”。新增一个候选不应改变已有候选的优劣关系——如果改变了，
          请在决策记录中写明你知道并接受这一点。
        </p>
      </div>
    </section>
  `,
})
export class ReversalPanelComponent {
  @Input() analysis: Analysis | null = null;

  get dyn() {
    return this.analysis?.rank_reversal.dynamic_anchors.reversals ?? [];
  }
  get fixed() {
    return this.analysis?.rank_reversal.fixed_anchors.reversals ?? [];
  }

  label(key: string): string {
    return this.analysis?.alternatives.find((a) => a.key === key)?.label ?? key;
  }
}
