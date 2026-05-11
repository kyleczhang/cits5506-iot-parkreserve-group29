// Centralized backend API configuration

const API_BASE_URL =
  process.env.REACT_APP_API_URL;

export const API_ENDPOINTS = {

  login:
    `${API_BASE_URL}/auth/login`,

  register:
    `${API_BASE_URL}/auth/register`,

  reservations:
    `${API_BASE_URL}/reservations`,

  wallet:
    `${API_BASE_URL}/wallet`

};

export default API_BASE_URL;