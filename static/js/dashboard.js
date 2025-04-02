document.addEventListener('DOMContentLoaded', function() {
    // Set current year for footer
    document.querySelector('.footer-container').innerHTML = 
        document.querySelector('.footer-container').innerHTML.replace('{{ current_year }}', new Date().getFullYear());
    
    // Highlight active navigation links
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-links a').forEach(link => {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('active');
        }
    });
    
    // Add sorting functionality to tables
    document.querySelectorAll('.data-table th').forEach((header, index) => {
        header.addEventListener('click', () => {
            sortTable(header.closest('table'), index);
        });
        header.style.cursor = 'pointer';
        header.title = 'Click to sort';
    });
});

// Table sorting function
function sortTable(table, column) {
    const tbody = table.querySelector('tbody');
    const rows = Array.from(tbody.querySelectorAll('tr'));
    const isNumeric = rows.length > 0 && !isNaN(parseFloat(rows[0].cells[column].textContent));
    const direction = table.getAttribute('data-sort-dir') === 'asc' ? -1 : 1;
    
    // Update sort direction
    if (table.getAttribute('data-sort-col') === column.toString()) {
        table.setAttribute('data-sort-dir', direction === 1 ? 'asc' : 'desc');
    } else {
        table.setAttribute('data-sort-col', column.toString());
        table.setAttribute('data-sort-dir', 'asc');
    }
    
    // Sort the rows
    rows.sort((a, b) => {
        const cellA = a.cells[column].textContent.trim();
        const cellB = b.cells[column].textContent.trim();
        
        if (isNumeric) {
            return direction * (parseFloat(cellA) - parseFloat(cellB));
        } else {
            return direction * cellA.localeCompare(cellB);
        }
    });
    
    // Reorder the rows
    rows.forEach(row => tbody.appendChild(row));
}