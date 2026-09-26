import React, { useState } from 'react';
import HeroSection from '../features/campaign/components/HeroSection';
import ProblemSection from '../features/campaign/components/ProblemSection';
import VisionSection from '../features/campaign/components/VisionSection';
import LearningSection from '../features/campaign/components/LearningSection';
import ActivitiesSection from '../features/campaign/components/ActivitiesSection';
import ParticipationSection from '../features/campaign/components/ParticipationSection';
import JoinSection from '../features/campaign/components/JoinSection';


export default function CommunityCampaignPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [preselectedRole, setPreselectedRole] = useState('');

  const handleRoleSelect = (role) => {
    setPreselectedRole(role);
    setModalOpen(true);
  };

  const handleOpenModal = () => {
    setPreselectedRole('');
    setModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-black text-white">
      <HeroSection onJoinClick={handleOpenModal} />
      <ProblemSection />
      <VisionSection />
      <LearningSection />
      <ActivitiesSection />
      <ParticipationSection onRoleSelect={handleRoleSelect} />
      <JoinSection
        isModalOpen={modalOpen}
        onOpenModal={handleOpenModal}
        onCloseModal={() => setModalOpen(false)}
        preselectedRole={preselectedRole}
      />
    </div>
  );
}
