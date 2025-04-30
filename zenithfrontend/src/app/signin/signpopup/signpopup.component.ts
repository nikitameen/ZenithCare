// dialog-example/dialog-example.component.ts
import { Component, Inject, OnInit, forwardRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { EventEmitter, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../auth/auth.service';
import { Router, ActivatedRoute } from '@angular/router';
import { ReactiveFormsModule } from '@angular/forms';

@Component({
  selector: 'app-signpopup',
  standalone: true, // I'm assuming this is a standalone component based on the imports
  imports: [CommonModule, MatDialogModule, MatButtonModule, FormsModule, ReactiveFormsModule],
  templateUrl: './signpopup.component.html',
  styleUrl: './signpopup.component.scss'
})
export class DialogExampleComponent implements OnInit {
  loginForm!: FormGroup;
  errorMessage: string = '';
  loading: boolean = false;
  public email: string = '';
  public password: string = '';
  
  @Output() close = new EventEmitter<void>();
  
  constructor(
    public dialogRef: MatDialogRef<DialogExampleComponent>,
    @Inject(MAT_DIALOG_DATA) public data: any,
    private fb: FormBuilder,
    @Inject(forwardRef(() => AuthService)) private authService: AuthService,
    private router: Router,
    private route: ActivatedRoute
  ) {
    this.loginForm = this.fb.group({
      email: ['', [Validators.required, Validators.email]],
      password: ['', [Validators.required, Validators.minLength(6)]]
    });
  }
  
  ngOnInit(): void {
    // Check for LinkedIn callback
    this.route.queryParams.subscribe(params => {
      const code = params['code'];
      const state = params['state'];
      const savedState = localStorage.getItem('linkedin_state');
      
      if (code && state && state === savedState) {
        this.loading = true;
        localStorage.removeItem('linkedin_state');
        
        this.authService.loginWithLinkedIn(code).subscribe({
          next: () => {
            this.router.navigate(['/dashboard']);
          },
          error: (error) => {
            this.errorMessage = 'LinkedIn login failed. Please try again.';
            this.loading = false;
          }
        });
      }
    });
  }
  
  onConfirm(): void {
    this.dialogRef.close({ confirmed: true });
  }
  
  onCancel(): void {
    this.dialogRef.close();
  }
  
  loginWithGoogle() {
    // Integrate Google OAuth here
    console.log('Google login triggered');
  }
  
  loginWithEmail() {
    // Add actual auth logic here
    console.log(`Email login: ${this.email}, ${this.password}`);
  }
  
  closeModal() {
    this.dialogRef.close();
    this.close.emit();
  }
  
  onSubmit(): void {
    if (this.loginForm.invalid) {
      return;
    }
    
    this.loading = true;
    const { email, password } = this.loginForm.value;
    
    this.authService.login(email, password).subscribe({
      next: () => {
        this.router.navigate(['/dashboard']);
      },
      error: (error) => {
        this.errorMessage = error.error?.message || 'Invalid email or password';
        this.loading = false;
      }
    });
  }
  
  loginWithLinkedIn(): void {
    window.location.href = this.authService.getLinkedInAuthUrl();
  }
}