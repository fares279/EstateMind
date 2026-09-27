import { render, screen } from '@testing-library/react';
import { LegalAnswerCard } from '../LegalAnswerCard';

const sources = [
  { law_name: 'Code des droits d’enregistrement', article: '20', similarity_score: 0.81, confidence_label: 'HIGH' },
  { law_name: 'Loi hypothécaire', article: '7', similarity_score: 0.64, confidence_label: 'MEDIUM' },
];

describe('LegalAnswerCard', () => {
  it('shows the answer and one citation per source', () => {
    render(<LegalAnswerCard answer="Le droit est de 5 %." sources={sources} grounding={85} confidenceLevel="HIGH" />);
    expect(screen.getByText('Le droit est de 5 %.')).toBeInTheDocument();
    expect(screen.getByText(/HIGH Grounding \(85%\)/)).toBeInTheDocument();
    expect(screen.getByText(/Article 20/)).toBeInTheDocument();
    expect(screen.getByText(/Article 7/)).toBeInTheDocument();
    expect(screen.queryByText(/Low grounding/)).not.toBeInTheDocument();
  });

  it('warns when grounding is low', () => {
    render(<LegalAnswerCard answer="Réponse incertaine." sources={[]} grounding={40} confidenceLevel="LOW" />);
    expect(screen.getByText(/Low grounding/)).toBeInTheDocument();
  });
});
