import { render, screen } from '@testing-library/react';
import i18n from '../../../i18n/config';
import { KeyboardShortcutsModal } from '../KeyboardNavigation';

describe('KeyboardShortcutsModal i18n', () => {
  it('renders shortcut descriptions in English when English is selected', async () => {
    const originalLanguage = i18n.language;
    await i18n.changeLanguage('en');
    const view = render(<KeyboardShortcutsModal isOpen onClose={() => {}} />);

    try {
      expect(screen.getByText('Navigate results')).toBeInTheDocument();
      expect(screen.getByText('Start download')).toBeInTheDocument();
      expect(screen.getByText('Toggle theme')).toBeInTheDocument();
      expect(screen.queryByText('Navegar entre resultados')).not.toBeInTheDocument();
      expect(screen.queryByText('Iniciar descarga')).not.toBeInTheDocument();
      expect(screen.queryByText('Cambiar tema')).not.toBeInTheDocument();
    } finally {
      view.unmount();
      await i18n.changeLanguage(originalLanguage);
    }
  });
});
