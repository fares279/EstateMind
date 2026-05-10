import React, { useState } from 'react';
import HeroSection from '../components/Campaign/HeroSection';
import ProblemSection from '../components/Campaign/ProblemSection';
import VisionSection from '../components/Campaign/VisionSection';
import LearningSection from '../components/Campaign/LearningSection';
import ActivitiesSection from '../components/Campaign/ActivitiesSection';
import ParticipationSection from '../components/Campaign/ParticipationSection';
import JoinSection from '../components/Campaign/JoinSection';


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
