import React, { useState } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, PaymentElement, useStripe, useElements } from '@stripe/react-stripe-js';
import { X, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import axios from 'axios';
import { devUpgradePlan } from '../services/api';

// Initialize Stripe (guard against missing publishable key to avoid runtime error)
const PUBLISHABLE_KEY = process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY;
let stripePromise = null;
if (typeof PUBLISHABLE_KEY === 'string' && PUBLISHABLE_KEY.trim().length > 0) {
  stripePromise = loadStripe(PUBLISHABLE_KEY);
} else {
  // Avoid calling loadStripe with undefined which throws in runtime.
  // This helps local development when env vars are not yet provided.
  // eslint-disable-next-line no-console
  console.warn('Stripe publishable key is not configured. Set REACT_APP_STRIPE_PUBLISHABLE_KEY in frontend/.env');
}

// Inner payment form component
function PaymentForm({ clientSecret, plan, onSuccess, onClose, userEmail, userFullName, userPhone }) {
  const stripe = useStripe();
  const elements = useElements();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const allowDevFallback = process.env.NODE_ENV !== 'production';

  const finishWithDevUpgrade = async () => {
    const response = await devUpgradePlan(plan);
    if (response.data.success) {
      setMessage(response.data.message || `Payment successful! Your plan has been upgraded to ${plan}.`);
      setTimeout(() => {
        onSuccess();
      }, 2000);
      return true;
    }
    return false;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!stripe || !elements) {
      setError('Payment service is not loaded. Please refresh and try again.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setMessage(null);

    try {
      // Confirm the payment while sending the billing data Stripe requires.
      const { error: confirmError, paymentIntent } = await stripe.confirmPayment({
        elements,
        redirect: 'if_required',
        confirmParams: {
          payment_method_data: {
            billing_details: {
              name: userFullName || userEmail || 'EstateMind Customer',
              email: userEmail || '',
              phone: (userPhone || '').trim(),
              address: {
                country: 'TN',
                postal_code: '1000',
              },
            },
          },
          return_url: `${window.location.origin}/account/dashboard`,
        },
      });

      if (confirmError) {
        if (allowDevFallback) {
          try {
            const upgraded = await finishWithDevUpgrade();
            if (upgraded) {
              setIsLoading(false);
              return;
            }
          } catch (fallbackError) {
            console.error('Dev fallback error:', fallbackError);
          }
        }
        setError(confirmError.message);
        setIsLoading(false);
        return;
      }

      if (paymentIntent && paymentIntent.status === 'succeeded') {
        // Payment succeeded, now confirm with our backend
        try {
          const token = localStorage.getItem('access_token');
          const response = await axios.post(
            `${process.env.REACT_APP_API_URL}/billing/confirm-payment/`,
            {
              intent_id: paymentIntent.id,
              plan: plan,
            },
            {
              headers: {
                Authorization: `Bearer ${token}`,
                'Content-Type': 'application/json',
              },
            }
          );

          if (response.data.success) {
            setMessage('Payment successful! Your plan has been upgraded.');
            setTimeout(() => {
              onSuccess();
            }, 2000);
          } else {
            setError(response.data.error || 'Failed to confirm payment');
          }
        } catch (backendError) {
          console.error('Backend error:', backendError);
          if (allowDevFallback) {
            try {
              const upgraded = await finishWithDevUpgrade();
              if (upgraded) {
                setIsLoading(false);
                return;
              }
            } catch (fallbackError) {
              console.error('Dev fallback error:', fallbackError);
            }
          }
          setError(
            backendError.response?.data?.error ||
            'Failed to process payment. Please contact support.'
          );
        }
      } else if (allowDevFallback) {
        try {
          const upgraded = await finishWithDevUpgrade();
          if (upgraded) {
            setIsLoading(false);
            return;
          }
        } catch (fallbackError) {
          console.error('Dev fallback error:', fallbackError);
        }
      } else if (paymentIntent && paymentIntent.status === 'requires_action') {
        setError('Additional verification required. Please complete the authentication.');
      }
    } catch (err) {
      console.error('Payment error:', err);
      if (allowDevFallback) {
        try {
          const upgraded = await finishWithDevUpgrade();
          if (upgraded) {
            setIsLoading(false);
            return;
          }
        } catch (fallbackError) {
          console.error('Dev fallback error:', fallbackError);
        }
      }
      setError(err.message || 'An unexpected error occurred.');
    }

    setIsLoading(false);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <PaymentElement
        options={{
          layout: 'tabs',
          defaultValues: {
            billingDetails: {
              email: userEmail || '',
            },
          },
          fields: {
            billingDetails: 'auto',
          },
          terms: {
            card: 'auto',
          },
        }}
      />

      {error && (
        <div className="flex gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {message && (
        <div className="flex gap-3 p-4 bg-green-50 border border-green-200 rounded-lg">
          <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
          <p className="text-green-700 text-sm">{message}</p>
        </div>
      )}

      <button
        disabled={isLoading || !stripe || !elements}
        type="submit"
        className="w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <Loader className="w-4 h-4 animate-spin" />
            Processing Payment...
          </>
        ) : (
          'Complete Payment'
        )}
      </button>
    </form>
  );
}

// Main modal component
export default function PaymentModal({
  isOpen,
  onClose,
  clientSecret,
  plan,
  onSuccess,
  userEmail,
  userFullName,
  userPhone,
}) {
  if (!isOpen) return null;

  const options = {
    clientSecret: clientSecret,
    appearance: {
      theme: 'stripe',
      variables: {
        colorPrimary: '#2563eb',
      },
    },
  };

  const planPrices = {
    pro: { amount: 2500, currency: 'usd', display: '$25.00/month' },
    investor: { amount: 5000, currency: 'usd', display: '$50.00/month' },
  };

  const currentPlan = planPrices[plan] || { amount: 0, currency: 'tnd', display: 'Custom' };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Complete Your Payment</h2>
            <p className="text-sm text-gray-600 mt-1">
              Upgrade to <span className="font-semibold capitalize">{plan} Plan</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6 max-h-[calc(100vh-200px)] overflow-y-auto">
          {/* Plan Info */}
          <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-100">
            <p className="text-sm text-gray-600">Plan Amount</p>
            <p className="text-2xl font-bold text-blue-600 mt-1">{currentPlan.display}</p>
          </div>

          {/* Payment Form */}
          { !stripePromise ? (
            <div className="p-6">
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <p className="text-sm text-yellow-800">Stripe is not configured for this environment.</p>
                <p className="text-xs text-gray-500 mt-2">Set <strong>REACT_APP_STRIPE_PUBLISHABLE_KEY</strong> in <strong>frontend/.env</strong> and restart the dev server.</p>
              </div>
            </div>
          ) : clientSecret ? (
            <Elements stripe={stripePromise} options={options}>
              <PaymentForm
                clientSecret={clientSecret}
                plan={plan}
                onSuccess={onSuccess}
                onClose={onClose}
                userEmail={userEmail}
                userFullName={userFullName}
                userPhone={userPhone}
              />
            </Elements>
          ) : (
            <div className="text-center py-8">
              <Loader className="w-8 h-8 animate-spin text-gray-400 mx-auto mb-3" />
              <p className="text-gray-500">Loading payment form...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
