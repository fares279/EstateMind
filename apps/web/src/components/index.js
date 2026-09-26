/**
 * EstateMind Intelligence Components Index
 * Central export point for shared UI components and domain-specific modules
 */

// Shared UI Components
export {
  FreshnessPill, ConfidenceBadge, ConfidenceBand, ProvenanceBlock, TrendBadge,
  SHAPDriver, SourceCitation, AnomalyAlert, FallbackNotice, SkeletonLoader,
  ErrorFallback
} from './shared/CommonComponents';

// Data Pipeline Status
export { DataFreshnessHeader } from '../features/dashboard/components/DataPipelineStatus';

// Delegation Intelligence
export { DelegationTooltip } from '../features/explore/components/DelegationTooltip';

// Market KPI Dashboard
export { FreshKPICard, KPIGrid } from '../features/dashboard/components/MarketKPIGrid';

// Property Valuation Engine
export { ValuationResultPanel } from '../features/valuation/components/PropertyValuationPanel';

// Legal Document Assistant
export { LegalAnswerCard, LegalQAInterface } from '../features/legal/components/LegalAnswerCard';

// Price Forecast Engine
export { ForecastFanChart } from '../features/forecast/components/PriceForecastChart';

// Investment Intelligence
export { InvestmentGradeCard, PortfolioRiskPanel } from '../features/invest/components/InvestmentGradeCard';

// Climate Risk Intelligence
export { ClimateRiskPanel } from '../features/climate/components/ClimateRiskPanel';

// AI Advisor
export { ChatMessage, ChatInterface } from '../features/advisor/components/AdvisorChatWidget';

// Market Simulator
export { ScenarioBuilder, SimulationResultPanel } from '../features/simulator/components/MarketSimulatorPanel';
