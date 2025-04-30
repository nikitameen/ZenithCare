import { Routes } from '@angular/router';

import { HomeComponent } from './components/home/home.component';
import { HcpComponent } from './components/hcp/hcp.component';
import { EmployerComponent } from './components/employer/employer.component';
import { FormularyComponent } from './components/formulary/formulary.component';
import { HospitalComponent } from './components/hospital/hospital.component';

export const routes: Routes = [
  { path: '', redirectTo: '/home', pathMatch: 'full' },
  { path: 'home', component: HomeComponent },
  { path: 'hcp', component: HcpComponent },
  { path: 'employer', component: EmployerComponent },
  { path: 'formulary', component: FormularyComponent },
  { path: 'hospital', component: HospitalComponent },
  { path: '**', redirectTo: '/home' } // Redirect to home for any unmatched routes
];