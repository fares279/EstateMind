import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { chatSendMessage } from '../../../../services/api';
import AIChatWidget from '../AIChatWidget';

jest.mock('../../../../services/api', () => ({ chatSendMessage: jest.fn() }));

beforeAll(() => {
  window.HTMLElement.prototype.scrollIntoView = jest.fn();
});

describe('AIChatWidget', () => {
  it('keeps focus in the input after sending with Enter, and shows text as typed', async () => {
    // CRA resets mock implementations before each test, so set it here
    let reply;
    chatSendMessage.mockReturnValue(new Promise((resolve) => { reply = resolve; }));
    const { container } = render(<AIChatWidget />);
    fireEvent.click(container.querySelector('button'));   // the floating open button
    const box = await screen.findByPlaceholderText(/Ask about prices/);
    // let the 'focus when opening' timer (200 ms) fire first, so it can't mask the result
    await act(() => new Promise((r) => setTimeout(r, 300)));
    box.focus();
    fireEvent.change(box, { target: { value: 'my name is bob' } });
    await act(async () => { fireEvent.keyDown(box, { key: 'Enter' }); });
    // Browsers drop focus from an input that becomes disabled while waiting; jsdom does not,
    // so do it here, then let the reply arrive.
    const elsewhere = document.createElement('button');
    document.body.appendChild(elsewhere);
    act(() => elsewhere.focus());
    expect(document.activeElement).not.toBe(box);
    await act(async () => { reply({ data: { message: 'Your name is bob.', session_id: 's1' } }); });
    await waitFor(() => expect(document.body.textContent).toContain('Your name is bob'));
    await waitFor(() => expect(document.activeElement).toBe(box));
    const typed = screen.getByText('my name is bob');
    expect(typed.className).not.toMatch(/uppercase/);
  });
});
