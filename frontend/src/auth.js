// Thin wrapper around amazon-cognito-identity-js: the only file that knows about Cognito.
// (If the app later moves to the Hosted UI / OAuth redirect, only this file changes.)
//
// Sign-in uses SRP: the password never leaves the browser, only a proof of it.
// The SDK keeps the tokens in localStorage and refreshes the access token with the
// refresh token when `getSession` finds it expired.
import { AuthenticationDetails, CognitoUser, CognitoUserPool } from 'amazon-cognito-identity-js'

const USER_POOL_ID = import.meta.env.VITE_COGNITO_USER_POOL_ID
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID

// Without Cognito config (local docker stack) the login is skipped entirely;
// the backend must then run with AUTH_DISABLED=true.
export const authEnabled = Boolean(USER_POOL_ID && CLIENT_ID)

export const NEW_PASSWORD_REQUIRED = 'NEW_PASSWORD_REQUIRED'
export const SIGNED_OUT_EVENT = 'auth:signed-out'

const pool = authEnabled ? new CognitoUserPool({ UserPoolId: USER_POOL_ID, ClientId: CLIENT_ID }) : null

export function signIn(email, password) {
  return new Promise((resolve, reject) => {
    const user = new CognitoUser({ Username: email, Pool: pool })
    user.authenticateUser(new AuthenticationDetails({ Username: email, Password: password }), {
      onSuccess: () => resolve(),
      onFailure: reject,
      // Users created by the admin must set a new password on first login.
      newPasswordRequired: () => reject(Object.assign(new Error(NEW_PASSWORD_REQUIRED), { code: NEW_PASSWORD_REQUIRED })),
    })
  })
}

// Resolves to the current valid session (refreshing it if needed) or null.
export function getSession() {
  return new Promise((resolve) => {
    const user = pool?.getCurrentUser()
    if (!user) return resolve(null)
    user.getSession((err, session) => resolve(!err && session?.isValid() ? session : null))
  })
}

export const sessionEmail = (session) => session?.getIdToken().payload.email ?? null

export async function getAccessToken() {
  const session = await getSession()
  return session ? session.getAccessToken().getJwtToken() : null
}

export function signOut() {
  // The callback form also revokes the refresh token on the Cognito side.
  pool?.getCurrentUser()?.signOut(() => {})
  window.dispatchEvent(new Event(SIGNED_OUT_EVENT))
}
