// Turn any request error into a sentence for users. Never shows raw exception text
// (axios' 'Request failed with status code 500', 'Network Error', stack details).
export function userErrorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const data = err?.response?.data;
  if (data && typeof data === 'object') {
    for (const key of ['error', 'detail', 'message']) {
      if (typeof data[key] === 'string' && data[key].trim()) return data[key];
    }
  }
  if (err && !err.response && (err.request || err.message === 'Network Error' || err.code === 'ECONNABORTED')) {
    return err.code === 'ECONNABORTED'
      ? 'The server took too long to respond. Please try again.'
      : 'Could not reach the server. Check your connection and try again.';
  }
  return fallback;
}
