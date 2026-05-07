// Toast notification
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    if (type === 'error') toast.style.background = '#ef4444';
    if (type === 'warning') toast.style.background = '#f59e0b';
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// Modal de confirmación genérico
function confirmModal(options) {
    return new Promise((resolve) => {
        let modal = document.getElementById('global-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'global-modal';
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <h3 id="modal-title">Confirmar</h3>
                    <p id="modal-message"></p>
                    <div style="display: flex; gap: 1rem; justify-content: flex-end; margin-top: 1.5rem;">
                        <button id="modal-cancel" class="btn-secondary">Cancelar</button>
                        <button id="modal-confirm" class="btn">Aceptar</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        document.getElementById('modal-title').innerText = options.title || 'Confirmar';
        document.getElementById('modal-message').innerText = options.message || '¿Estás seguro?';
        modal.style.display = 'flex';
        const confirmBtn = document.getElementById('modal-confirm');
        const cancelBtn = document.getElementById('modal-cancel');
        const cleanup = () => {
            modal.style.display = 'none';
            confirmBtn.removeEventListener('click', onConfirm);
            cancelBtn.removeEventListener('click', onCancel);
        };
        const onConfirm = () => {
            cleanup();
            resolve(true);
        };
        const onCancel = () => {
            cleanup();
            resolve(false);
        };
        confirmBtn.addEventListener('click', onConfirm);
        cancelBtn.addEventListener('click', onCancel);
    });
}

// Mejorar todos los formularios con confirmación si tienen clase 'confirmar'
document.addEventListener('DOMContentLoaded', () => {
    // Confirmación para acciones peligrosas
    document.querySelectorAll('form[data-confirm]').forEach(form => {
        form.addEventListener('submit', async (e) => {
            const message = form.getAttribute('data-confirm') || '¿Confirmas esta acción?';
            const confirmed = await confirmModal({ message });
            if (!confirmed) {
                e.preventDefault();
                showToast('Acción cancelada', 'warning');
            }
        });
    });

    // Animación de entrada para tarjetas
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, i) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        setTimeout(() => {
            card.style.transition = 'all 0.4s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, i * 50);
    });

    // Tooltips simples
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(el => {
        el.addEventListener('mouseenter', (e) => {
            const tip = document.createElement('div');
            tip.textContent = el.getAttribute('data-tooltip');
            tip.style.position = 'absolute';
            tip.style.background = '#1f2937';
            tip.style.color = '#fff';
            tip.style.padding = '4px 8px';
            tip.style.borderRadius = '8px';
            tip.style.fontSize = '12px';
            tip.style.whiteSpace = 'nowrap';
            tip.style.zIndex = '1000';
            const rect = el.getBoundingClientRect();
            tip.style.top = rect.top - 30 + window.scrollY + 'px';
            tip.style.left = rect.left + 'px';
            tip.id = 'temp-tooltip';
            document.body.appendChild(tip);
        });
        el.addEventListener('mouseleave', () => {
            const tip = document.getElementById('temp-tooltip');
            if (tip) tip.remove();
        });
    });
});

// Exportar funciones globales para usar en consola o eventos inline
window.showToast = showToast;
window.confirmModal = confirmModal;