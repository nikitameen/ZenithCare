import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { RouterModule } from '@angular/router';
import { CommonModule } from '@angular/common';
import { MatDialog } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { provideHttpClient } from '@angular/common/http';
@Component({
  selector: 'app-root',
  imports: [CommonModule, MatButtonModule,RouterModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent {
  title = 'Zenith Healthcare';
  constructor(private dialog: MatDialog) {}
  
  openDialog(): void {
    import('./signin/signpopup/signpopup.component').then(module => {
      const dialogRef = this.dialog.open(module.DialogExampleComponent, {
        width: '400px',
        data: { message: 'Hello from ZenithCare!' }
      });
      
      dialogRef.afterClosed().subscribe(result => {
        console.log('Dialog closed with result:', result);
      });
    });
  }
}

