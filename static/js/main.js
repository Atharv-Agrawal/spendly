function applyPreset(preset) {
    const today = new Date();
    const pad = n => String(n).padStart(2, '0');
    const fmt = d => `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
    const fromInput = document.getElementById('from');
    const toInput = document.getElementById('to');
    const presetInput = document.getElementById('preset-input');

    if (preset === 'all') {
        fromInput.value = '';
        toInput.value = '';
        presetInput.value = '';
    } else {
        const from = new Date(today);
        if (preset === 'month') {
            from.setDate(1);
            presetInput.value = 'month';
        } else if (preset === '3months') {
            from.setMonth(from.getMonth() - 3);
            presetInput.value = '3months';
        } else if (preset === '6months') {
            from.setMonth(from.getMonth() - 6);
            presetInput.value = '6months';
        }
        fromInput.value = fmt(from);
        toInput.value = fmt(today);
    }
    document.getElementById('filter-form').submit();
}
