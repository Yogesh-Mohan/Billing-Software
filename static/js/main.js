// RED STUDIO main javascript helpers

document.addEventListener('DOMContentLoaded', function () {
    // Sidebar toggle for mobile/responsive views
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', function () {
            sidebar.classList.toggle('active');
        });
    }

    // Auto-dismiss alert boxes after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            let bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});

// Helper functions for Edit Modal Population
function populateCustomerEdit(id, name, phone, email, address) {
    document.getElementById('edit_customer_id').value = id;
    document.getElementById('edit_name').value = name;
    document.getElementById('edit_phone').value = phone;
    document.getElementById('edit_email').value = email;
    document.getElementById('edit_address').value = address;
}

function populateProductEdit(id, name, code, category, price, stock) {
    document.getElementById('edit_product_id').value = id;
    document.getElementById('edit_product_name').value = name;
    document.getElementById('edit_product_code').value = code;
    document.getElementById('edit_category').value = category;
    document.getElementById('edit_price').value = price;
    document.getElementById('edit_stock_quantity').value = stock;
}

// Item code lookup for invoices
function initializeItemLookup() {
    document.addEventListener('change', function(e) {
        if (e.target && e.target.classList.contains('item-code-input')) {
            lookupItemByCode(e.target);
        }
    });
}

function lookupItemByCode(inputElement) {
    const itemCode = inputElement.value.trim().toUpperCase();
    const row = inputElement.closest('tr') || inputElement.closest('.item-row');
    
    if (!itemCode || !row) return;
    
    const itemNameInput = row.querySelector('[name*="item_name"], .item-name-input, [data-field="item_name"]');
    const quantityInput = row.querySelector('[name*="item_quantity"], .item-quantity-input, [data-field="quantity"]');
    const priceInput = row.querySelector('[name*="item_price"], .item-price-input, [data-field="price"]');
    
    if (!itemNameInput) return;
    
    fetch(`/api/item/${encodeURIComponent(itemCode)}`)
        .then(response => {
            if (response.ok) {
                return response.json();
            } else {
                throw new Error('Item not found');
            }
        })
        .then(data => {
            if (itemNameInput) {
                itemNameInput.value = data.item_name;
                itemNameInput.setAttribute('data-item-id', data._id);
            }
            if (quantityInput) {
                quantityInput.value = data.quantity || '';
            }
            if (priceInput) {
                priceInput.value = data.price || '';
            }
        })
        .catch(error => {
            if (itemNameInput) itemNameInput.value = '';
            if (quantityInput) quantityInput.value = '';
            if (priceInput) priceInput.value = '';
            console.warn('Item lookup failed:', error);
        });
}

// Initialize item lookup on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeItemLookup();
});
