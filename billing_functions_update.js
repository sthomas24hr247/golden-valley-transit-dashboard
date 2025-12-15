        function showGenerateClaims() {
            // Create modal for generating claims
            const modal = document.createElement('div');
            modal.id = 'claimsModal';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:1000;';
            modal.innerHTML = `
                <div style="background:white;border-radius:12px;padding:30px;max-width:600px;width:90%;max-height:80vh;overflow-y:auto;">
                    <h2 style="margin-bottom:20px;color:#1a1a2e;">Generate New Claim</h2>
                    <div id="tripsList" style="margin-bottom:20px;">
                        <p>Loading completed trips...</p>
                    </div>
                    <div style="margin-bottom:15px;">
                        <label style="display:block;margin-bottom:5px;font-weight:600;">Trip ID:</label>
                        <input type="text" id="claimTripId" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;" placeholder="Enter trip ID">
                    </div>
                    <div style="margin-bottom:15px;">
                        <label style="display:block;margin-bottom:5px;font-weight:600;">Service Type:</label>
                        <select id="claimServiceType" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;">
                            <option value="ambulatory">Ambulatory</option>
                            <option value="wheelchair">Wheelchair</option>
                            <option value="stretcher">Stretcher</option>
                        </select>
                    </div>
                    <div style="margin-bottom:20px;">
                        <label style="display:block;margin-bottom:5px;font-weight:600;">Mileage:</label>
                        <input type="number" id="claimMileage" step="0.1" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;" placeholder="Enter mileage" value="10">
                    </div>
                    <div style="display:flex;gap:10px;">
                        <button onclick="generateClaim()" style="flex:1;padding:12px;background:#5b6be8;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Generate Claim</button>
                        <button onclick="closeModal('claimsModal')" style="flex:1;padding:12px;background:#ccc;color:#333;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Cancel</button>
                    </div>
                    <div id="claimResult" style="margin-top:15px;"></div>
                </div>
            `;
            document.body.appendChild(modal);
            loadCompletedTrips();
        }

        async function loadCompletedTrips() {
            try {
                const response = await fetch('/api/analytics/operational?days=30');
                const data = await response.json();
                document.getElementById('tripsList').innerHTML = '<p style="color:#666;font-size:14px;">Enter a Trip ID from completed trips to generate a claim.</p>';
            } catch (error) {
                document.getElementById('tripsList').innerHTML = '<p style="color:#fc8181;">Could not load trips</p>';
            }
        }

        async function generateClaim() {
            const tripId = document.getElementById('claimTripId').value;
            const serviceType = document.getElementById('claimServiceType').value;
            const mileage = document.getElementById('claimMileage').value;

            if (!tripId) {
                document.getElementById('claimResult').innerHTML = '<p style="color:#fc8181;">Please enter a Trip ID</p>';
                return;
            }

            try {
                const response = await fetch('/api/billing/generate-claim', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ trip_id: tripId, service_type: serviceType, mileage: parseFloat(mileage) })
                });
                const data = await response.json();

                if (data.success) {
                    document.getElementById('claimResult').innerHTML = `
                        <div style="background:#d4edda;padding:15px;border-radius:6px;margin-top:10px;">
                            <p style="color:#155724;font-weight:600;">Claim Generated Successfully!</p>
                            <p>Claim Number: <strong>${data.claim_number}</strong></p>
                            <p>Amount: <strong>$${data.total_amount.toFixed(2)}</strong></p>
                            <p>Insurance: ${data.insurance_company}</p>
                        </div>
                    `;
                    setTimeout(() => { closeModal('claimsModal'); loadBillingData(); }, 3000);
                } else {
                    document.getElementById('claimResult').innerHTML = `<p style="color:#fc8181;">${data.error || 'Failed to generate claim'}</p>`;
                }
            } catch (error) {
                document.getElementById('claimResult').innerHTML = `<p style="color:#fc8181;">Error: ${error.message}</p>`;
            }
        }

        function showPendingClaims() {
            const modal = document.createElement('div');
            modal.id = 'pendingModal';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:1000;';
            modal.innerHTML = `
                <div style="background:white;border-radius:12px;padding:30px;max-width:800px;width:90%;max-height:80vh;overflow-y:auto;">
                    <h2 style="margin-bottom:20px;color:#1a1a2e;">Pending Claims</h2>
                    <div id="pendingClaimsList">Loading...</div>
                    <div style="margin-top:20px;">
                        <button onclick="closeModal('pendingModal')" style="padding:12px 24px;background:#ccc;color:#333;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Close</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            loadPendingClaims();
        }

        async function loadPendingClaims() {
            try {
                const response = await fetch('/api/billing/pending-claims');
                const data = await response.json();

                if (data.claims && data.claims.length > 0) {
                    let html = '<table style="width:100%;border-collapse:collapse;">';
                    html += '<tr style="background:#f5f5f5;"><th style="padding:10px;text-align:left;">Claim #</th><th style="padding:10px;">Amount</th><th style="padding:10px;">Insurance</th><th style="padding:10px;">Action</th></tr>';
                    data.claims.forEach(claim => {
                        html += `<tr style="border-bottom:1px solid #eee;">
                            <td style="padding:10px;">${claim.claim_number}</td>
                            <td style="padding:10px;">$${claim.total_amount.toFixed(2)}</td>
                            <td style="padding:10px;">${claim.insurance_company}</td>
                            <td style="padding:10px;"><button onclick="submitClaim('${claim.claim_id}')" style="padding:6px 12px;background:#5b6be8;color:white;border:none;border-radius:4px;cursor:pointer;">Submit</button></td>
                        </tr>`;
                    });
                    html += '</table>';
                    document.getElementById('pendingClaimsList').innerHTML = html;
                } else {
                    document.getElementById('pendingClaimsList').innerHTML = '<p style="color:#666;">No pending claims found.</p>';
                }
            } catch (error) {
                document.getElementById('pendingClaimsList').innerHTML = `<p style="color:#fc8181;">Error: ${error.message}</p>`;
            }
        }

        async function submitClaim(claimId) {
            try {
                const response = await fetch('/api/billing/submit-claim', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ claim_id: claimId })
                });
                const data = await response.json();
                if (data.success) {
                    alert('Claim submitted to clearinghouse successfully!');
                    loadPendingClaims();
                } else {
                    alert('Error: ' + (data.error || 'Failed to submit claim'));
                }
            } catch (error) {
                alert('Error: ' + error.message);
            }
        }

        function showPaymentEntry() {
            const modal = document.createElement('div');
            modal.id = 'paymentModal';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:1000;';
            modal.innerHTML = `
                <div style="background:white;border-radius:12px;padding:30px;max-width:500px;width:90%;">
                    <h2 style="margin-bottom:20px;color:#1a1a2e;">Post Payment</h2>
                    <div style="margin-bottom:15px;">
                        <label style="display:block;margin-bottom:5px;font-weight:600;">Claim ID:</label>
                        <input type="text" id="paymentClaimId" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;" placeholder="Enter claim ID">
                    </div>
                    <div style="margin-bottom:15px;">
                        <label style="display:block;margin-bottom:5px;font-weight:600;">Payment Amount ($):</label>
                        <input type="number" id="paymentAmount" step="0.01" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;" placeholder="0.00">
                    </div>
                    <div style="margin-bottom:15px;">
                        <label style="display:block;margin-bottom:5px;font-weight:600;">Payment Reference:</label>
                        <input type="text" id="paymentReference" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;" placeholder="Check # or EFT reference">
                    </div>
                    <div style="margin-bottom:20px;">
                        <label style="display:block;margin-bottom:5px;font-weight:600;">Payment Date:</label>
                        <input type="date" id="paymentDate" style="width:100%;padding:10px;border:1px solid #ddd;border-radius:6px;" value="${new Date().toISOString().split('T')[0]}">
                    </div>
                    <div style="display:flex;gap:10px;">
                        <button onclick="postPayment()" style="flex:1;padding:12px;background:#22c55e;color:white;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Post Payment</button>
                        <button onclick="closeModal('paymentModal')" style="flex:1;padding:12px;background:#ccc;color:#333;border:none;border-radius:6px;cursor:pointer;font-weight:600;">Cancel</button>
                    </div>
                    <div id="paymentResult" style="margin-top:15px;"></div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        async function postPayment() {
            const claimId = document.getElementById('paymentClaimId').value;
            const amount = document.getElementById('paymentAmount').value;
            const reference = document.getElementById('paymentReference').value;
            const date = document.getElementById('paymentDate').value;

            if (!claimId || !amount) {
                document.getElementById('paymentResult').innerHTML = '<p style="color:#fc8181;">Please enter Claim ID and Amount</p>';
                return;
            }

            try {
                const response = await fetch('/api/billing/post-payment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        claim_id: claimId,
                        payment_amount: parseFloat(amount),
                        payment_reference: reference,
                        payment_date: date
                    })
                });
                const data = await response.json();

                if (data.success) {
                    document.getElementById('paymentResult').innerHTML = `
                        <div style="background:#d4edda;padding:15px;border-radius:6px;">
                            <p style="color:#155724;font-weight:600;">Payment Posted Successfully!</p>
                            <p>Amount: $${data.payment_amount.toFixed(2)}</p>
                            <p>New Status: ${data.new_status}</p>
                        </div>
                    `;
                    setTimeout(() => { closeModal('paymentModal'); loadBillingData(); }, 2000);
                } else {
                    document.getElementById('paymentResult').innerHTML = `<p style="color:#fc8181;">${data.error || 'Failed to post payment'}</p>`;
                }
            } catch (error) {
                document.getElementById('paymentResult').innerHTML = `<p style="color:#fc8181;">Error: ${error.message}</p>`;
            }
        }

        function closeModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) modal.remove();
        }

        loadBillingData();
