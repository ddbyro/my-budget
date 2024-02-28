function confirmAction(event) {
    if (!confirm("Are you sure you want to perform this action?")) {
        event.preventDefault();
    }
}
function validateForm() {
    var due_date = document.getElementById('due_date').value;
    var bill_name = document.getElementById('bill_name').value;
    var amount_due = document.getElementById('amount_due').value;

    if (!due_date || !bill_name || !amount_due) {
        alert("Error: All fields are required");
    } else {
        // Submit the form
        document.querySelector('form').submit();
    }
}
document.getElementById('entryForm').addEventListener('submit', function(event) {
    var dueDate = document.getElementById('due_date').value;
    var billName = document.getElementById('bill_name').value;
    var amountDue = document.getElementById('amount_due').value;
    if (!dueDate || !billName || !amountDue) {
        alert('All fields are required');
        event.preventDefault();
    }
});
window.addEventListener('DOMContentLoaded', (event) => {
    flatpickr("#due_date", {});
});