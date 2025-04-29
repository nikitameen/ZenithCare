


// dialog-example/dialog-example.component.ts
import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import {  EventEmitter, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
@Component({
  selector: 'app-signpopup',
  imports: [CommonModule, MatDialogModule, MatButtonModule,FormsModule],
  templateUrl: './signpopup.component.html',
  styleUrl: './signpopup.component.scss'
  
  
})
export class DialogExampleComponent {
  constructor(
    public dialogRef: MatDialogRef<DialogExampleComponent>,
    @Inject(MAT_DIALOG_DATA) public data: any
  ) {}
  public email: string = '';
  public password: string = '';
  @Output() close = new EventEmitter<void>();
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

  loginWithLinkedIn() {
    // Integrate LinkedIn OAuth here
    console.log('LinkedIn login triggered');
  }

  loginWithEmail() {
    // Add actual auth logic here
    console.log(`Email login: ${this.email}, ${this.password}`);
  }

  closeModal() {
    this.dialogRef.close();
    this.close.emit();
  }
}



