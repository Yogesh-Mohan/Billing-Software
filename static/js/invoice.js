// RED STUDIO - Brisk Invoice layout calculations

document.addEventListener('DOMContentLoaded', function () {
    const addRowBtn = document.getElementById('add-item-row');
    const itemsTableBody = document.getElementById('invoice-items-body');
    const taxRateInput = document.getElementById('tax_rate');
    
    if (addRowBtn) {
        addRowBtn.addEventListener('click', function () {
            addNewRow();
        });
    }

    if (taxRateInput) {
        taxRateInput.addEventListener('input', calculateInvoiceTotals);
    }

    const amountPaidInput = document.getElementById('amount_paid');
    if (amountPaidInput) {
        amountPaidInput.addEventListener('input', calculateInvoiceTotals);
    }

    // Default Row Initialization
    if (itemsTableBody && itemsTableBody.rows.length === 0) {
        addNewRow();
    }

    function addNewRow() {
        const row = document.createElement('tr');
        row.className = 'invoice-item-row';
        
        let options = '';
        itemsData.forEach(function (item) {
            options += `<option value="${item.code}">${item.name}</option>`;
        });

        // Generate a unique ID for the datalist
        const rowId = 'datalist_' + Math.random().toString(36).substr(2, 9);

        row.innerHTML = `
            <td>
                <input type="number" name="item_quantity[]" class="form-control form-control-custom quantity-input" min="1" value="1" required disabled>
                <div class="stock-warning text-danger mt-1 small" style="font-size: 7.5pt; display:none;"></div>
            </td>
            <td>
                <input type="text" name="item_code[]" class="form-control form-control-custom code-input" placeholder="Item Code" list="${rowId}" required autocomplete="off">
                <datalist id="${rowId}">
                    ${options}
                </datalist>
                <input type="hidden" name="item_product_id[]" class="item-id-hidden">
            </td>
            <td>
                <input type="text" name="item_description[]" class="form-control form-control-custom description-input" placeholder="Description" required readonly>
            </td>
            <td>
                <input type="number" name="item_price[]" class="form-control form-control-custom price-input" step="0.01" min="0" required readonly>
            </td>
            <td>
                <select class="form-select form-control-custom row-tax-select">
                    <option value="0" selected>[None]</option>
                    <option value="18">[GST 18%]</option>
                </select>
            </td>
            <td>
                <input type="number" name="item_discount[]" class="form-control form-control-custom discount-input" step="0.01" min="0" max="100" value="0" placeholder="0">
            </td>
            <td>
                <input type="number" class="form-control form-control-custom subtotal-input" step="0.01" value="0.00" readonly>
            </td>
            <td>
                <button type="button" class="btn btn-link text-danger remove-row-btn p-0" style="text-decoration: none;"><i class="fas fa-times fs-5"></i></button>
            </td>
        `;

        itemsTableBody.appendChild(row);

        const codeInput = row.querySelector('.code-input');
        const hiddenId = row.querySelector('.item-id-hidden');
        const qty = row.querySelector('.quantity-input');
        const price = row.querySelector('.price-input');
        const desc = row.querySelector('.description-input');
        const removeBtn = row.querySelector('.remove-row-btn');
        const rowTaxSelect = row.querySelector('.row-tax-select');
        const discountInput = row.querySelector('.discount-input');
        const warningEl = row.querySelector('.stock-warning');

        codeInput.addEventListener('input', function () {
            const val = codeInput.value.trim().toUpperCase();
            const matchedItem = itemsData.find(i => i.code.toUpperCase() === val);
            
            if (matchedItem) {
                hiddenId.value = matchedItem.id;
                price.value = parseFloat(matchedItem.price).toFixed(2);
                price.removeAttribute('readonly');
                
                desc.value = matchedItem.description || matchedItem.name;
                desc.removeAttribute('readonly');
                
                qty.disabled = false;
                qty.value = 1;
                
                if (matchedItem.stock !== -1) {
                    qty.max = matchedItem.stock;
                    warningEl.innerText = `${matchedItem.stock} left`;
                    warningEl.style.display = 'block';
                } else {
                    qty.removeAttribute('max');
                    warningEl.style.display = 'none';
                }
                
                calculateRowSubtotal(row);
            }
        });

        qty.addEventListener('input', function () {
            const maxVal = parseInt(qty.max) || 0;
            const curVal = parseInt(qty.value) || 0;
            const warningEl = row.querySelector('.stock-warning');
            // Fix #10: Use inline warning instead of blocking alert()
            if (curVal > maxVal && maxVal > 0) {
                qty.value = maxVal;
                warningEl.innerText = `⚠ Max stock: ${maxVal} units`;
                warningEl.style.color = '#dc3545';
                warningEl.style.display = 'block';
            } else if (maxVal > 0) {
                warningEl.innerText = `${maxVal - curVal} remaining`;
                warningEl.style.color = '#9ca3af';
                warningEl.style.display = 'block';
            }
            calculateRowSubtotal(row);
        });

        price.addEventListener('input', function () {
            calculateRowSubtotal(row);
        });

        rowTaxSelect.addEventListener('change', function () {
            calculateRowSubtotal(row);
        });

        discountInput.addEventListener('input', function () {
            calculateRowSubtotal(row);
        });

        removeBtn.addEventListener('click', function () {
            row.remove();
            calculateInvoiceTotals();
        });
    }

    function calculateRowSubtotal(row) {
        const qty = parseInt(row.querySelector('.quantity-input').value) || 0;
        const price = parseFloat(row.querySelector('.price-input').value) || 0;
        const discountPct = parseFloat(row.querySelector('.discount-input').value) || 0;
        const baseAmount = qty * price;
        const discountAmount = baseAmount * (discountPct / 100);
        const subtotal = baseAmount - discountAmount;
        row.querySelector('.subtotal-input').value = subtotal.toFixed(2);
        calculateInvoiceTotals();
    }

    function calculateInvoiceTotals() {
        let subtotalSum = 0;
        let totalDiscount = 0;
        const rows = document.querySelectorAll('.invoice-item-row');
        
        rows.forEach(function (row) {
            const qty = parseInt(row.querySelector('.quantity-input').value) || 0;
            const price = parseFloat(row.querySelector('.price-input').value) || 0;
            const discountPct = parseFloat(row.querySelector('.discount-input').value) || 0;
            const baseAmount = qty * price;
            const discountAmount = baseAmount * (discountPct / 100);
            totalDiscount += discountAmount;
            subtotalSum += parseFloat(row.querySelector('.subtotal-input').value) || 0;
        });

        const taxRate = parseFloat(taxRateInput.value) || 0;
        const taxAmount = subtotalSum * (taxRate / 100);
        const grandTotal = subtotalSum + taxAmount;

        const amountPaidInput = document.getElementById('amount_paid');
        const amountPaid = amountPaidInput ? (parseFloat(amountPaidInput.value) || 0) : 0;
        const balanceDue = Math.max(0, grandTotal - amountPaid);

        document.getElementById('display_subtotal').innerText = subtotalSum.toFixed(2);
        document.getElementById('display_discount_total').innerText = totalDiscount.toFixed(2);
        document.getElementById('display_tax_amount').innerText = taxAmount.toFixed(2);
        document.getElementById('display_grand_total').innerText = grandTotal.toFixed(2);
        
        const balanceDueEl = document.getElementById('display_balance_due');
        if (balanceDueEl) {
            balanceDueEl.innerText = balanceDue.toFixed(2);
        }
    }
});
