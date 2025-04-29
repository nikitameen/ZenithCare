


// dialog-example/dialog-example.component.ts
import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-signpopup',
  imports: [CommonModule, MatDialogModule, MatButtonModule],
  templateUrl: './signpopup.component.html',
  styleUrl: './signpopup.component.scss'
  
  
})
export class DialogExampleComponent {
  constructor(
    public dialogRef: MatDialogRef<DialogExampleComponent>,
    @Inject(MAT_DIALOG_DATA) public data: any
  ) {}
  
  onConfirm(): void {
    this.dialogRef.close({ confirmed: true });
  }
  
  onCancel(): void {
    this.dialogRef.close();
  }
}