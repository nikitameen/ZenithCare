import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { tap } from 'rxjs/operators';
import { Router } from '@angular/router';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private apiUrl = 'http://localhost:3000/api';
  private tokenKey = 'auth_token';
  private userSubject = new BehaviorSubject<any>(null);
  public user$ = this.userSubject.asObservable();
  
  constructor(private http: HttpClient, private router: Router) {
    this.loadUser();
  }
  
  public get currentUserValue(): any {
    return this.userSubject.value;
  }
  
  private loadUser() {
    const token = this.getToken();
    if (token) {
      // Get user info if token exists
      this.getUserProfile().subscribe({
        error: () => {
          // Handle error like token expiration
          this.logout();
        }
      });
    }
  }
  
  login(email: string, password: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/auth/login`, { email, password })
      .pipe(
        tap(response => {
          this.setToken(response.token);
          this.userSubject.next(response.user);
        })
      );
  }
  
  register(userData: any): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/auth/register`, userData);
  }
  
  loginWithLinkedIn(code: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/auth/linkedin`, { code })
      .pipe(
        tap(response => {
          this.setToken(response.token);
          this.userSubject.next(response.user);
        })
      );
  }
  
  getUserProfile(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/users/me`)
      .pipe(
        tap(user => {
          this.userSubject.next(user);
        })
      );
  }
  
  logout(): void {
    localStorage.removeItem(this.tokenKey);
    this.userSubject.next(null);
    this.router.navigate(['/login']);
  }
  
  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }
  
  setToken(token: string): void {
    localStorage.setItem(this.tokenKey, token);
  }
  
  isAuthenticated(): boolean {
    return !!this.getToken();
  }
  
  getLinkedInAuthUrl(): string {
    const clientId = 'YOUR_LINKEDIN_CLIENT_ID';
    const redirectUri = encodeURIComponent('http://localhost:4200/login');
    const state = this.generateRandomString(16);
    localStorage.setItem('linkedin_state', state);
    
    return `https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=${clientId}&redirect_uri=${redirectUri}&state=${state}&scope=r_liteprofile%20r_emailaddress`;
  }
  
  private generateRandomString(length: number): string {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
      result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
  }
}