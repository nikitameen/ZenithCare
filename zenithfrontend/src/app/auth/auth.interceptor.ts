import { Injectable } from '@angular/core';
import { HttpRequest, HttpHandler, HttpEvent, HttpInterceptor } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from './auth.service';
import { environment } from '../../environments/environment';

@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  constructor(private authService: AuthService) { }

  intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    // Add auth header with JWT if user is logged in and request is to the API URL
    const currentUser = this.authService.currentUserValue;
    const token = this.authService.getToken();
    
    // Check if request is to the API URL
    // You should have environment.apiUrl defined in your environment files
    const apiUrl = environment.apiUrl || 'http://localhost:3000/api';
    const isApiUrl = request.url.startsWith(apiUrl);
    
    if (token && isApiUrl) {
      request = request.clone({
        setHeaders: {
          Authorization: `Bearer ${token}`
        }
      });
    }

    return next.handle(request);
  }
}