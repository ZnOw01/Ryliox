import { render, screen } from '@testing-library/react';
import { act } from 'react';
import { BeautifulToastContainer, useToastStore } from '../BeautifulToast';

function addToast(type: 'success' | 'error' | 'warning' | 'info' | 'loading') {
  act(() => {
    useToastStore.getState().addToast({ type, message: `Test ${type}` });
  });
}

beforeEach(() => {
  act(() => {
    useToastStore.getState().clearAll();
  });
});

describe('BeautifulToast ARIA', () => {
  it('renders error toasts with role="alert" and without aria-live="polite"', () => {
    addToast('error');
    render(<BeautifulToastContainer />);

    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).not.toHaveAttribute('aria-live', 'polite');
  });

  it('renders warning toasts with role="alert" and without aria-live="polite"', () => {
    addToast('warning');
    render(<BeautifulToastContainer />);

    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
    expect(alert).not.toHaveAttribute('aria-live', 'polite');
  });

  it('renders success toasts with aria-live="polite" and without role="alert"', () => {
    addToast('success');
    render(<BeautifulToastContainer />);

    const region = screen.getByText(/Test success/).closest('[aria-live="polite"]');
    expect(region).toBeInTheDocument();
    expect(region).not.toHaveAttribute('role', 'alert');
  });

  it('renders info toasts with aria-live="polite" and without role="alert"', () => {
    addToast('info');
    render(<BeautifulToastContainer />);

    const region = screen.getByText(/Test info/).closest('[aria-live="polite"]');
    expect(region).toBeInTheDocument();
    expect(region).not.toHaveAttribute('role', 'alert');
  });

  it('renders loading toasts with aria-live="polite" and without role="alert"', () => {
    addToast('loading');
    render(<BeautifulToastContainer />);

    const region = screen.getByText(/Test loading/).closest('[aria-live="polite"]');
    expect(region).toBeInTheDocument();
    expect(region).not.toHaveAttribute('role', 'alert');
  });
});

describe('BeautifulToast store', () => {
  it('does not expose pauseToast or resumeToast', () => {
    const state = useToastStore.getState();
    expect(state).not.toHaveProperty('pauseToast');
    expect(state).not.toHaveProperty('resumeToast');
  });
});
