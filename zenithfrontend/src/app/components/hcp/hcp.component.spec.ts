import { ComponentFixture, TestBed } from '@angular/core/testing';

import { HcpComponent } from './hcp.component';

describe('HcpComponent', () => {
  let component: HcpComponent;
  let fixture: ComponentFixture<HcpComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HcpComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(HcpComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
