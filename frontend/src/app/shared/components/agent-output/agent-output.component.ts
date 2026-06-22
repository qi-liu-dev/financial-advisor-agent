import { ChangeDetectionStrategy, Component, Input } from '@angular/core';
import { PercentPipe } from '@angular/common';
import { AgentOutput } from '../../../core/api/api.models';

@Component({
  selector: 'app-agent-output',
  imports: [PercentPipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="output-grid">
      <section class="summary card-section">
        <div class="eyebrow">Executive summary</div>
        <p>{{ output.summary }}</p>
        <div class="confidence">
          <span>Model confidence</span><strong>{{ output.confidence | percent: '1.0-0' }}</strong>
        </div>
      </section>
      <section class="card-section">
        <h3>Key points</h3>
        <ul>
          @for (item of output.key_points; track item) {
            <li>{{ item }}</li>
          }
        </ul>
      </section>
      <section class="card-section risk">
        <h3>Risks</h3>
        @if (output.risks.length) {
          <ul>
            @for (item of output.risks; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        } @else {
          <p class="muted">No risks returned.</p>
        }
      </section>
      <section class="card-section">
        <h3>Next actions</h3>
        @if (output.next_actions.length) {
          <ol>
            @for (item of output.next_actions; track item) {
              <li>{{ item }}</li>
            }
          </ol>
        } @else {
          <p class="muted">No next actions returned.</p>
        }
      </section>
      @if (asClientSummary().suitability_context?.length) {
        <section class="card-section">
          <h3>Suitability context</h3>
          <ul>
            @for (item of asClientSummary().suitability_context; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        </section>
      }
      @if (asClientSummary().missing_information?.length) {
        <section class="card-section warning">
          <h3>Missing information</h3>
          <ul>
            @for (item of asClientSummary().missing_information; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        </section>
      }
      @if (asMeetingNotes().decisions?.length) {
        <section class="card-section">
          <h3>Decisions</h3>
          <ul>
            @for (item of asMeetingNotes().decisions; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        </section>
      }
      @if (asMeetingNotes().follow_up_questions?.length) {
        <section class="card-section">
          <h3>Follow-up questions</h3>
          <ul>
            @for (item of asMeetingNotes().follow_up_questions; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        </section>
      }
      @if (asInvestmentReview().suitability_observations?.length) {
        <section class="card-section">
          <h3>Suitability observations</h3>
          <ul>
            @for (item of asInvestmentReview().suitability_observations; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        </section>
      }
      @if (asInvestmentReview().compliance_flags?.length) {
        <section class="card-section risk">
          <h3>Compliance flags</h3>
          <ul>
            @for (item of asInvestmentReview().compliance_flags; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        </section>
      }
      @if (asInvestmentReview().questions_for_advisor?.length) {
        <section class="card-section">
          <h3>Questions for advisor</h3>
          <ul>
            @for (item of asInvestmentReview().questions_for_advisor; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        </section>
      }
      <section class="card-section citations">
        <h3>Citations to input</h3>
        @if (output.citations_to_input.length) {
          <ul>
            @for (item of output.citations_to_input; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        } @else {
          <p class="muted">No citations returned.</p>
        }
      </section>
    </div>
  `,
  styleUrl: './agent-output.component.scss',
})
export class AgentOutputComponent {
  @Input({ required: true }) output!: AgentOutput;
  asClientSummary(): AgentOutput & {
    suitability_context?: string[];
    missing_information?: string[];
  } {
    return this.output;
  }
  asMeetingNotes(): AgentOutput & { decisions?: string[]; follow_up_questions?: string[] } {
    return this.output;
  }
  asInvestmentReview(): AgentOutput & {
    suitability_observations?: string[];
    compliance_flags?: string[];
    questions_for_advisor?: string[];
  } {
    return this.output;
  }
}
