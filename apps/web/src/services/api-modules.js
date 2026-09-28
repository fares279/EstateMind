import api, {
	chatSendMessage,
	getClimateDashboard,
	getClimateWeather,
	getForecastDelegation,
	getForecastGovernorate,
	getForecastNational,
	getInvestorDashboard,
	getKpiFreshness,
	simStart,
} from './api';

export * from './api';

export const sendChatMessage = (message, sessionId) => {
	if (message && typeof message === 'object') {
		return chatSendMessage(message).then((response) => response.data);
	}

	return chatSendMessage({ message, session_id: sessionId }).then((response) => response.data);
};

// The API only accepts feedback with the conversation's session_id.
export const submitChatFeedback = (responseLogId, sessionId, feedback, feedbackText = '') =>
	api.post('/chatbot/feedback/', {
		response_log_id: responseLogId,
		session_id: sessionId,
		feedback: feedback === 'helpful' ? 'thumbs_up' : 'thumbs_down',
		feedback_text: feedbackText,
	}).then((response) => response.data);

export const getClimateRisk = (lat, lon, delegation) => {
	if (delegation) {
		return api.get(`/climate/delegation/${encodeURIComponent(delegation)}/`).then((response) => response.data);
	}

	if (lat != null && lon != null) {
		return api.get('/climate/point/', { params: { lat, lon } }).then((response) => response.data);
	}

	return getClimateDashboard().then((response) => response.data);
};

export const getForecast = (delegationOrGovernorate, propertyType = 'apartment') => {
	if (delegationOrGovernorate && typeof delegationOrGovernorate === 'string') {
		return getForecastDelegation(delegationOrGovernorate, propertyType).then((response) => response.data);
	}

	if (delegationOrGovernorate?.governorate) {
		return getForecastGovernorate(delegationOrGovernorate.governorate, propertyType).then((response) => response.data);
	}

	return getForecastNational(propertyType).then((response) => response.data);
};

export const getScraperPipelineHealth = () =>
	api.get('/scraper/health/dashboard/').then((response) => response.data);

export const validateScenario = (scenario) => {
	const numericFields = [
		'interest_rate_shock',
		'construction_supply_shock',
		'foreign_investment_increase',
		'price_growth_target',
	];

	const issues = numericFields.filter((field) => typeof scenario?.[field] !== 'number' || Number.isNaN(scenario[field]));

	return Promise.resolve({
		is_valid: issues.length === 0,
		issues,
	});
};

export const runSimulation = (scenario) =>
	simStart({
		scenario_name: scenario?.scenario_name || scenario?.scenario || 'baseline',
		num_months: scenario?.num_months || 12,
		agent_scale: scenario?.agent_scale || 'tiny',
		seed: scenario?.seed || 2026,
		policy_overrides: scenario,
	}).then((response) => response.data);

export const getInvestmentGrade = (payload) =>
	api.post('/investor/scan/', payload).then((response) => response.data);

export const getPortfolioRisk = (portfolioId) =>
	api.get('/investor/risk/', { params: portfolioId ? { portfolio_id: portfolioId } : {} }).then((response) => response.data);

export default api;
