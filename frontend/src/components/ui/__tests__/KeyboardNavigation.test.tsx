import { fireEvent, render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import i18n from '../../../i18n/config';
import { KeyboardShortcutsModal, useKeyboardShortcuts } from '../KeyboardNavigation';

describe('KeyboardShortcutsModal i18n', () => {
  it('renders shortcut descriptions in English when English is selected', async () => {
    const originalLanguage = i18n.language;
    await i18n.changeLanguage('en');
    const view = render(<KeyboardShortcutsModal isOpen onClose={() => {}} />);

    try {
      expect(screen.getByText('Navigate results')).toBeInTheDocument();
      expect(screen.getByText('Toggle theme')).toBeInTheDocument();
      expect(screen.queryByText('Navegar entre resultados')).not.toBeInTheDocument();
      expect(screen.queryByText('Cambiar tema')).not.toBeInTheDocument();
    } finally {
      view.unmount();
      await i18n.changeLanguage(originalLanguage);
    }
  });

  it('lists only shortcuts the app binds', () => {
    render(<KeyboardShortcutsModal isOpen onClose={() => {}} />);

    expect(screen.queryByText('Foco en búsqueda')).toBeNull();
    expect(screen.queryByText('Limpiar búsqueda')).toBeNull();
    expect(screen.queryByText('Iniciar descarga')).toBeNull();
    expect(screen.queryByText('Cancelar descarga')).toBeNull();
  });
});

function ShortcutProbe({ onHelp }: { onHelp: () => void }) {
  useKeyboardShortcuts([{ key: '?', action: onHelp, description: 'help' }]);
  return <input aria-label="field" />;
}

describe('useKeyboardShortcuts', () => {
  it('fires a symbol shortcut typed with Shift', () => {
    const onHelp = vi.fn();
    render(<ShortcutProbe onHelp={onHelp} />);

    fireEvent.keyDown(document.body, { key: '?', shiftKey: true });

    expect(onHelp).toHaveBeenCalledTimes(1);
  });

  it('leaves the key alone while the user types in a field', () => {
    const onHelp = vi.fn();
    render(<ShortcutProbe onHelp={onHelp} />);

    fireEvent.keyDown(screen.getByLabelText('field'), { key: '?', shiftKey: true });

    expect(onHelp).not.toHaveBeenCalled();
  });

  it('lets a global symbol shortcut through to a field instead of stealing the character', () => {
    const onHelp = vi.fn();
    function GlobalProbe() {
      useKeyboardShortcuts([{ key: '?', action: onHelp, description: 'help', scope: 'global' }]);
      return <input aria-label="search" />;
    }
    render(<GlobalProbe />);

    fireEvent.keyDown(screen.getByLabelText('search'), { key: '?', shiftKey: true });

    expect(onHelp).not.toHaveBeenCalled();
  });
});
